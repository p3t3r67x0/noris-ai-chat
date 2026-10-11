"""Production handshake and ticket flow through Uvicorn's actual proxy middleware."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.types import ASGIApp
from starlette.websockets import WebSocketDisconnect
from uvicorn._types import ASGI3Application
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from noris_ai.chat.generation import GenerationManager, Peer
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.tickets import WsTicketStore
from noris_ai.core.config import EnvironmentSettings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.main import create_app

ORIGIN = "https://chat.oklabflensburg.de"
HOST = "chat.oklabflensburg.de"
AUTH = ("fixture-user", "fixture-application-password-never-real")
CADDY_IP = "10.0.0.20"
HEADERS = {
    "origin": ORIGIN,
    "host": HOST,
    "x-forwarded-proto": "https",
    "x-forwarded-for": "203.0.113.10, 10.0.0.10",
}


@dataclass
class Handshake:
    client: TestClient
    store: WsTicketStore
    manager: GenerationManager
    repository: AsyncMock

    def protocols(self) -> list[str]:
        response = self.client.post("/api/v1/chat/ws-ticket", auth=AUTH, headers=HEADERS, json={})
        assert response.status_code == 200
        assert response.json()["expiresInSeconds"] == 60
        assert response.headers["cache-control"] == "no-store"
        return ["noris-chat.v1", "ticket." + response.json()["ticketId"]]


@pytest.fixture
def handshake() -> Iterator[Handshake]:
    config = EnvironmentSettings(
        environment="production",
        llm_provider="disabled",
        llm_allowed_origins=(ORIGIN,),
        llm_access_username=AUTH[0],
        llm_access_password=SecretStr(AUTH[1]),
        llm_api_key=SecretStr("fixture-provider-key-never-real"),
        chat_ws_allowed_hosts=(),
        chat_ws_ticket_ttl_seconds=60,
    )
    app = create_app(config)
    repository = AsyncMock(spec=ChatRepository)
    store = WsTicketStore(60)
    manager = GenerationManager(config, cast(ChatRepository, repository), LLMGateway(config, None))
    app.state.chat_settings = config
    app.state.chat_tickets = store
    app.state.chat_generations = manager
    proxy_headers = ProxyHeadersMiddleware(cast(ASGI3Application, app), trusted_hosts=CADDY_IP)
    # Inject only the repository; use the real routes, ticket store, manager and
    # middleware. Avoid application lifespan and all external DB/provider access.
    client = TestClient(cast(ASGIApp, proxy_headers), client=(CADDY_IP, 8000))
    try:
        yield Handshake(client, store, manager, repository)
    finally:
        client.close()


@pytest.mark.parametrize("forwarded_proto", ["https", "wss"])
def test_https_nginx_caddy_ticket_then_wss(handshake: Handshake, forwarded_proto: str) -> None:
    protocols = handshake.protocols()
    handshake.repository.prune_stream_events.assert_awaited_once_with(168)
    with handshake.client.websocket_connect(
        "/api/v1/chat/ws",
        headers=HEADERS | {"x-forwarded-proto": forwarded_proto},
        subprotocols=protocols,
    ) as socket:
        assert socket.accepted_subprotocol == "noris-chat.v1"
        assert socket.receive_json()["type"] == "chat.connected"
        socket.send_json({"version": 1, "type": "chat.ping"})
        assert socket.receive_json()["type"] == "chat.pong"
    assert not handshake.manager.peers
    assert not handshake.store.redeem(protocols[1].removeprefix("ticket."))


def test_direct_wss_accepts_valid_ticket(handshake: Handshake) -> None:
    with handshake.client.websocket_connect(
        f"wss://{HOST}/api/v1/chat/ws",
        headers={"origin": ORIGIN},
        subprotocols=handshake.protocols(),
    ) as socket:
        assert socket.receive_json()["type"] == "chat.connected"


@pytest.mark.parametrize(
    ("headers", "protocols", "reason"),
    [
        ({"origin": "https://evil.example"}, None, "ORIGIN_NOT_ALLOWED"),
        ({"origin": ""}, None, "ORIGIN_NOT_ALLOWED"),
        ({"host": "evil.example"}, None, "HOST_NOT_ALLOWED"),
        ({"host": "["}, None, "HOST_NOT_ALLOWED"),
        ({"host": "backend:8000", "x-forwarded-host": HOST}, None, "HOST_NOT_ALLOWED"),
        ({"x-forwarded-proto": "http"}, None, "INVALID_SCHEME"),
        ({"x-forwarded-proto": "ws"}, None, "INVALID_SCHEME"),
        ({"x-forwarded-proto": "https, http"}, None, "INVALID_SCHEME"),
        ({"x-forwarded-proto": ""}, None, "INVALID_SCHEME"),
        ({}, ["ticket.fixture-ticket-never-real"], "MISSING_SUBPROTOCOL"),
        ({}, ["noris-chat.v1"], "MISSING_TICKET_SUBPROTOCOL"),
        (
            {},
            ["noris-chat.v1", "ticket.first", "ticket.second"],
            "MULTIPLE_TICKET_SUBPROTOCOLS",
        ),
        ({}, ["noris-chat.v1", "ticket."], "TICKET_INVALID_OR_EXPIRED"),
        ({}, ["noris-chat.v1", "ticket.fixture-ticket-never-real"], "TICKET_INVALID_OR_EXPIRED"),
    ],
)
def test_handshake_rejection_diagnostics(
    handshake: Handshake,
    headers: dict[str, str],
    protocols: list[str] | None,
    reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    issued = handshake.protocols()
    with (
        pytest.raises(WebSocketDisconnect) as rejected,
        handshake.client.websocket_connect(
            "/api/v1/chat/ws", headers=HEADERS | headers, subprotocols=protocols or issued
        ),
    ):
        pass
    assert rejected.value.code == 1008
    assert f"reason={reason}" in caplog.text
    assert issued[1] not in caplog.text
    assert AUTH[1] not in caplog.text
    assert "fixture-provider-key-never-real" not in caplog.text
    assert "fixture-ticket-never-real" not in caplog.text
    assert not handshake.manager.peers
    # Earlier security failures must not consume a legitimate ticket.
    assert handshake.store.redeem(issued[1].removeprefix("ticket."))


def test_expired_ticket_is_rejected(
    handshake: Handshake, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Patch the module reference instead of the global time module used by asyncio.
    from types import SimpleNamespace

    import noris_ai.chat.tickets as tickets

    now = 100.0
    monkeypatch.setattr(tickets, "time", SimpleNamespace(monotonic=lambda: now))
    protocols = handshake.protocols()
    now += 60
    with (
        pytest.raises(WebSocketDisconnect) as rejected,
        handshake.client.websocket_connect(
            "/api/v1/chat/ws", headers=HEADERS.copy(), subprotocols=protocols
        ),
    ):
        pass
    assert rejected.value.code == 1008
    assert "reason=TICKET_INVALID_OR_EXPIRED" in caplog.text
    assert protocols[1] not in caplog.text


def test_missing_origin_is_rejected(handshake: Handshake, caplog: pytest.LogCaptureFixture) -> None:
    headers = {key: value for key, value in HEADERS.items() if key != "origin"}
    protocols = handshake.protocols()
    with (
        pytest.raises(WebSocketDisconnect) as rejected,
        handshake.client.websocket_connect(
            "/api/v1/chat/ws", headers=headers, subprotocols=protocols
        ),
    ):
        pass
    assert rejected.value.code == 1008
    assert "reason=ORIGIN_NOT_ALLOWED" in caplog.text
    assert handshake.store.redeem(protocols[1].removeprefix("ticket."))


def test_ticket_ttl_starts_after_retention_cleanup(
    handshake: Handshake, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    import noris_ai.chat.tickets as tickets

    now = 100.0
    monkeypatch.setattr(tickets, "time", SimpleNamespace(monotonic=lambda: now))

    async def slow_cleanup(hours: int) -> None:
        nonlocal now
        assert hours == 168
        now += 61

    handshake.repository.prune_stream_events.side_effect = slow_cleanup
    with handshake.client.websocket_connect(
        "/api/v1/chat/ws", headers=HEADERS.copy(), subprotocols=handshake.protocols()
    ) as socket:
        assert socket.receive_json()["type"] == "chat.connected"


def test_untrusted_client_cannot_spoof_wss(
    handshake: Handshake, caplog: pytest.LogCaptureFixture
) -> None:
    client = TestClient(handshake.client.app, client=("203.0.113.10", 8000))
    protocols = handshake.protocols()
    try:
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/api/v1/chat/ws", headers=HEADERS.copy(), subprotocols=protocols
            ),
        ):
            pass
    finally:
        client.close()
    assert "reason=INVALID_SCHEME" in caplog.text
    assert "scheme=ws" in caplog.text
    assert handshake.store.redeem(protocols[1].removeprefix("ticket."))


def test_logs_never_echo_untrusted_headers(
    handshake: Handshake, caplog: pytest.LogCaptureFixture
) -> None:
    protocols = handshake.protocols()
    sensitive_value = "fixture-sensitive-header-never-real"
    with (
        pytest.raises(WebSocketDisconnect),
        handshake.client.websocket_connect(
            "/api/v1/chat/ws",
            headers={
                "origin": sensitive_value,
                "host": sensitive_value,
                "x-forwarded-proto": sensitive_value,
            },
            subprotocols=[*protocols, sensitive_value],
        ),
    ):
        pass
    assert "reason=ORIGIN_NOT_ALLOWED" in caplog.text
    assert sensitive_value not in caplog.text
    assert protocols[1] not in caplog.text


@pytest.mark.parametrize(
    ("headers", "auth", "status"),
    [
        (HEADERS, None, 401),
        (HEADERS, (AUTH[0], "wrong-fixture-password"), 401),
        (HEADERS | {"origin": "https://evil.example"}, AUTH, 403),
        (HEADERS | {"sec-fetch-site": "cross-site"}, AUTH, 403),
    ],
)
def test_ticket_issue_requires_auth_and_allowed_write_origin(
    handshake: Handshake, headers: dict[str, str], auth: tuple[str, str] | None, status: int
) -> None:
    if auth is None:
        response = handshake.client.post("/api/v1/chat/ws-ticket", headers=headers, json={})
    else:
        response = handshake.client.post(
            "/api/v1/chat/ws-ticket", headers=headers, auth=auth, json={}
        )
    assert response.status_code == status
    handshake.repository.prune_stream_events.assert_not_awaited()


def test_capacity_rejection_is_diagnosed(
    handshake: Handshake, caplog: pytest.LogCaptureFixture
) -> None:
    import asyncio

    protocols = handshake.protocols()
    handshake.manager.peers.update(Peer(asyncio.Queue()) for _ in range(64))
    with (
        pytest.raises(WebSocketDisconnect) as rejected,
        handshake.client.websocket_connect(
            "/api/v1/chat/ws", headers=HEADERS.copy(), subprotocols=protocols
        ),
    ):
        pass
    assert rejected.value.code == 1013
    assert "reason=CONNECTION_LIMIT" in caplog.text
    assert protocols[1] not in caplog.text
