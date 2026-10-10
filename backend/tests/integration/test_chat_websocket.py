"""Actual FastAPI WebSockets with PostgreSQL; no external provider calls."""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.models import ChatStreamEvent
from noris_ai.chat.repository import ModelDatabase
from noris_ai.chat.service import ChatService
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import LLMModel
from noris_ai.llm.titles import TITLE_INSTRUCTION
from noris_ai.main import create_app
from tests.fixtures.provider_catalog import provider_model

pytestmark = pytest.mark.integration
AUTH = ("fixture-user", "fixture-application-password-never-real")
ORIGIN = {"origin": "http://localhost:3000", "host": "localhost:3000"}


class Simulator:
    def __init__(self) -> None:
        self.calls: list[list[ProviderMessage]] = []
        self.finished = False

    async def discover_models(self) -> list[ProviderModel]:
        return [
            provider_model(value)
            for value in [
                "fixture-alpha",
                "fixture-beta",
                "vllm/qsu/glm-5-3-flash",
                "vllm/release/gpt-oss-120b",
            ]
        ]

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        if messages[0].role == "system" and messages[0].content == TITLE_INSTRUCTION:
            yield "Persistente Gespräche"
            return
        self.calls.append(list(messages))
        self.finished = False
        if messages[0].role == "system":
            yield "Fortsetzung."
            return
        if messages[-1].content == "/error":
            raise LLMError("NETWORK_ERROR")
        yield "Hallo 🌍 "
        if messages[-1].content == "/length":
            raise LLMError("OUTPUT_LIMIT")
        await asyncio.sleep(0.25)
        if messages[-1].content == "/slow":
            await asyncio.sleep(10)
        yield "aus PostgreSQL."
        self.finished = True

    async def aclose(self) -> None:
        pass


@pytest.fixture
def simulator() -> Simulator:
    return Simulator()


@pytest.fixture
def client(
    migration_config: Config, llm_config: Settings, simulator: Simulator
) -> Iterator[TestClient]:
    command.upgrade(migration_config, "head")
    config = Settings(
        **(
            llm_config.model_dump()
            | {
                "database_url": os.environ["NORIS_TEST_DATABASE_URL"],
                "chat_disconnect_grace_seconds": 0.3,
                "llm_requests_per_minute": 120,
                "llm_daily_token_budget": 1_000_000,
            }
        )
    )
    with TestClient(
        create_app(config, provider=simulator), base_url="http://localhost:3000"
    ) as http:
        yield http


def protocols(client: TestClient) -> list[str]:
    response = client.post("/api/v1/chat/ws-ticket", auth=AUTH, headers=ORIGIN.copy(), json={})
    assert response.status_code == 200, response.text
    return ["noris-chat.v1", "ticket." + response.json()["ticketId"]]


def generate(client: TestClient, content: str = "Frage") -> dict[str, object]:
    response = client.post("/api/v1/conversations", auth=AUTH, json={}, headers=ORIGIN.copy())
    assert response.status_code == 201
    return {
        "version": 1,
        "type": "chat.generate",
        "requestId": str(uuid4()),
        "conversationId": response.json()["id"],
        "conversationVersion": 1,
        "inputMessageId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "modelId": "fixture-alpha",
        "content": content,
        "parentMessageId": None,
    }


def test_ticket_auth_origin_host_and_single_use(client: TestClient) -> None:
    assert client.post("/api/v1/chat/ws-ticket", json={}).status_code == 401
    ticket = protocols(client)
    for headers in ({"origin": "https://evil.example"}, ORIGIN | {"host": "evil.example"}, {}):
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/api/v1/chat/ws", subprotocols=ticket, headers=headers),
        ):
            pass
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=ticket, headers=ORIGIN.copy()
    ) as socket:
        assert socket.receive_json()["type"] == "chat.connected"
        socket.send_json({"version": 1, "type": "chat.ping"})
        assert socket.receive_json()["type"] == "chat.pong"
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/v1/chat/ws", subprotocols=ticket, headers=ORIGIN.copy()),
    ):
        pass


def test_stream_persistence_and_idempotence(client: TestClient, simulator: Simulator) -> None:
    payload = generate(client)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        sequences: list[int] = []
        text = ""
        while True:
            event = socket.receive_json()
            if "seq" not in event:
                continue
            sequences.append(event["seq"])
            assert event["generationId"] == payload["requestId"]
            if event["type"] == "chat.generation.delta":
                if not text:
                    assert not simulator.finished, (
                        "First chunk must arrive before provider completion"
                    )
                text += event["delta"]
            if event["type"] == "chat.generation.completed":
                assert event["content"] == text == "Hallo 🌍 aus PostgreSQL."
                break
        assert sequences == list(range(1, len(sequences) + 1))
        socket.send_json(payload)
        while socket.receive_json().get("type") != "chat.generation.completed":
            pass
        assert len(simulator.calls) == 1
    rows = client.get(
        f"/api/v1/conversations/{payload['conversationId']}/messages", auth=AUTH
    ).json()["messages"]
    assert [m["role"] for m in rows] == ["user", "assistant"]
    assert rows[1]["content"] == text and rows[1]["status"] == "completed"


def test_disconnect_reconnect_replay_and_snapshot(client: TestClient, simulator: Simulator) -> None:
    payload = generate(client)
    received, text = 0, ""
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while not text:
            event = socket.receive_json()
            received = event.get("seq", received)
            text += event.get("delta", "")
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": payload["requestId"],
                "lastReceivedSeq": received,
            }
        )
        while True:
            event = socket.receive_json()
            if "seq" in event:
                assert event["seq"] > received
                received = event["seq"]
                text += event.get("delta", "")
            if event["type"] == "chat.generation.completed":
                break
        assert text == "Hallo 🌍 aus PostgreSQL." and len(simulator.calls) == 1

    async def remove_replay() -> None:
        database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)
        async with database() as session, session.begin():
            await session.execute(delete(ChatStreamEvent))

    assert client.portal is not None
    client.portal.call(remove_replay)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": payload["requestId"],
                "lastReceivedSeq": 0,
            }
        )
        assert socket.receive_json()["type"] == "chat.resume.accepted"
        snapshot = socket.receive_json()
        assert snapshot["type"] == "chat.resume.snapshot" and snapshot["content"] == text
        assert snapshot["status"] == "completed"


def test_stop_and_provider_error(client: TestClient) -> None:
    for prompt, terminal in (("/slow", "cancelled"), ("/error", "failed")):
        payload = generate(client, prompt)
        with client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as socket:
            socket.receive_json()
            socket.send_json(payload)
            while True:
                event = socket.receive_json()
                if event["type"] == "chat.generation.delta" and prompt == "/slow":
                    socket.send_json(
                        {"version": 1, "type": "chat.cancel", "generationId": payload["requestId"]}
                    )
                if event["type"] == "chat.generation." + terminal:
                    break
        rows = client.get(
            f"/api/v1/conversations/{payload['conversationId']}/messages", auth=AUTH
        ).json()["messages"]
        assert rows[-1]["status"] == terminal


def test_server_path_regeneration_and_edit_preserve_variants(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client)

    def run(command_payload: dict[str, object]) -> None:
        with client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as socket:
            socket.receive_json()
            socket.send_json(command_payload)
            while True:
                event = socket.receive_json()
                assert event["type"] != "chat.error", event
                if event["type"] == "chat.generation.completed":
                    break

    run(payload)
    path = f"/api/v1/conversations/{payload['conversationId']}"
    regenerated = payload | {
        "requestId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "conversationVersion": client.get(path, auth=AUTH).json()["version"],
    }
    run(regenerated)
    edited = payload | {
        "requestId": str(uuid4()),
        "inputMessageId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "content": "Neue Frage",
        "editedFromMessageId": payload["inputMessageId"],
        "conversationVersion": client.get(path, auth=AUTH).json()["version"],
    }
    run(edited)
    rows = client.get(path + "/messages", auth=AUTH).json()["messages"]
    assert len(rows) == 5
    assert [[m.content for m in call] for call in simulator.calls] == [
        ["Frage"],
        ["Frage"],
        ["Neue Frage"],
    ]


def test_disconnect_grace_expires_as_interrupted(client: TestClient) -> None:
    payload = generate(client, "/slow")
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while socket.receive_json()["type"] != "chat.generation.delta":
            pass
    assert client.portal is not None
    client.portal.call(asyncio.sleep, 0.6)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": payload["requestId"],
                "lastReceivedSeq": 0,
            }
        )
        while True:
            event = socket.receive_json()
            if event["type"] == "chat.generation.interrupted":
                assert event["content"] == "Hallo 🌍 "
                break


def test_foreign_owner_and_budget_limits(client: TestClient, simulator: Simulator) -> None:
    app = cast(FastAPI, client.app)
    service = cast(ChatService, app.state.chat_service)
    manager = cast(GenerationManager, app.state.chat_generations)
    assert client.portal is not None
    foreign = client.portal.call(service.create_conversation, uuid4(), "Fremd")
    payload = generate(client)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload | {"conversationId": str(foreign.id)})
        assert socket.receive_json()["code"] == "NOT_FOUND"
        manager.gateway.config = manager.gateway.config.model_copy(
            update={"llm_daily_token_budget": 1}
        )
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            if event["type"] == "chat.generation.failed":
                assert event["code"] == "BUDGET_LIMIT"
                break
    assert not simulator.calls


def receive_terminal(
    socket: WebSocketTestSession, payload: dict[str, object], terminal: str
) -> dict[str, object]:
    socket.send_json(payload)
    while True:
        event = socket.receive_json()
        assert event["type"] != "chat.error", event
        if event["type"] == "chat.generation." + terminal:
            return event


def test_incomplete_continuation_preserves_original_and_snapshot_prefix(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "/length")
    path = f"/api/v1/conversations/{payload['conversationId']}"
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        first = receive_terminal(socket, payload, "incomplete")
        assert first["content"] == "Hallo 🌍 "
        continued = payload | {
            "requestId": str(uuid4()),
            "assistantMessageId": str(uuid4()),
            "conversationVersion": client.get(path, auth=AUTH).json()["version"],
            "operation": "continue",
            "sourceAssistantMessageId": payload["assistantMessageId"],
        }
        final = receive_terminal(socket, continued, "completed")
        assert final["content"] == "Hallo 🌍 Fortsetzung."
        socket.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": continued["requestId"],
                "lastReceivedSeq": 0,
            }
        )
        while True:
            event = socket.receive_json()
            if event["type"] == "chat.resume.snapshot":
                assert event["content"] == final["content"] and event["status"] == "completed"
                break
    rows = client.get(path + "/messages", auth=AUTH).json()["messages"]
    by_id = {m["id"]: m for m in rows}
    assert by_id[payload["assistantMessageId"]]["content"] == first["content"]
    assert by_id[payload["assistantMessageId"]]["status"] == "incomplete"
    assert by_id[continued["assistantMessageId"]]["continuationCount"] == 1
    assert simulator.calls[-1][2].content == first["content"]


@pytest.mark.parametrize("model", ["vllm/qsu/glm-5-3-flash", "vllm/release/gpt-oss-120b"])
def test_glm_and_gpt_simulators_share_the_persisted_gateway(client: TestClient, model: str) -> None:
    payload = generate(client) | {"modelId": model}
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        final = receive_terminal(socket, payload, "completed")
        assert final["content"] == "Hallo 🌍 aus PostgreSQL."


def test_startup_recovery_and_slow_client_overflow(client: TestClient) -> None:
    manager = cast(GenerationManager, cast(FastAPI, client.app).state.chat_generations)
    payload = generate(client)
    assert client.portal is not None
    client.portal.call(
        manager.repository.begin_generation,
        manager.config.chat_owner_id,
        GenerateIncomingMessage.model_validate(payload),
    )
    assert (
        client.portal.call(
            manager.repository.mark_running_generations_interrupted, manager.config.chat_owner_id
        )
        == 1
    )
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": payload["requestId"],
                "lastReceivedSeq": 0,
            }
        )
        assert socket.receive_json()["type"] == "chat.resume.accepted"
        assert socket.receive_json()["status"] == "interrupted"

        async def overflow() -> None:
            for _ in range(1000):
                manager.broadcast({"version": 1, "type": "chat.heartbeat"})

        client.portal.call(overflow)
        with pytest.raises(WebSocketDisconnect) as closed:
            while True:
                socket.receive_json()
        assert closed.value.code == 1013


def test_thousand_message_context_reaches_the_existing_provider(
    migration_config: Config, llm_config: Settings, simulator: Simulator
) -> None:
    """UI windows must never truncate the authoritative provider path."""
    from sqlalchemy import insert, update

    from noris_ai.chat.models import ChatConversation, ChatMessage

    command.upgrade(migration_config, "head")
    config = Settings(
        **(
            llm_config.model_dump()
            | {
                "database_url": os.environ["NORIS_TEST_DATABASE_URL"],
                "llm_models": tuple(
                    model.model_copy(update={"context_window": 131072})
                    for model in llm_config.llm_models
                ),
                "llm_daily_token_budget": 1_000_000,
            }
        )
    )
    with TestClient(
        create_app(config, provider=simulator), base_url="http://localhost:3000"
    ) as client:
        payload = generate(client)
        conversation_id = UUID(str(payload["conversationId"]))
        ids = [uuid4() for _ in range(1002)]
        alternate = uuid4()

        async def seed_path() -> None:
            database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)
            async with database() as session, session.begin():
                for index, id in enumerate(ids):
                    await session.execute(
                        insert(ChatMessage).values(
                            id=id,
                            conversation_id=conversation_id,
                            parent_message_id=ids[index - 1] if index else None,
                            role="user" if index % 2 == 0 else "assistant",
                            content=f"Selected {index}",
                            status="completed",
                        )
                    )
                await session.execute(
                    insert(ChatMessage).values(
                        id=alternate,
                        conversation_id=conversation_id,
                        parent_message_id=ids[1000],
                        role="assistant",
                        content="Not selected",
                        status="completed",
                    )
                )
                await session.execute(
                    update(ChatConversation)
                    .where(ChatConversation.id == conversation_id)
                    .values(active_leaf_message_id=ids[-1])
                )

        assert client.portal is not None
        client.portal.call(seed_path)
        assert (
            len(
                client.get(
                    f"/api/v1/conversations/{conversation_id}/active-path", auth=AUTH
                ).json()["messages"]
            )
            == 50
        )
        payload["parentMessageId"] = str(ids[-1])
        with client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as socket:
            socket.receive_json()
            socket.send_json(payload)
            while True:
                event = socket.receive_json()
                assert event["type"] != "chat.generation.failed", event
                if event["type"] == "chat.generation.completed":
                    break
        assert len(simulator.calls) == 1
        context = simulator.calls[0]
        assert len(context) == 1003
        assert [m.content for m in context[:-1]] == [f"Selected {i}" for i in range(1002)]
        assert all(m.content != "Not selected" for m in context)
        # A cached older boundary remains valid after appending this response.
        page = client.get(
            f"/api/v1/conversations/{conversation_id}/active-path",
            params={"beforeMessageId": str(ids[951])},
            auth=AUTH,
        )
        assert page.status_code == 200 and len(page.json()["messages"]) == 50
