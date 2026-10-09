import asyncio

import pytest
from pydantic import TypeAdapter, ValidationError

from noris_ai.chat.generation import Peer
from noris_ai.chat.tickets import WsTicketStore
from noris_ai.chat.ws_protocol import ClientMessage
from noris_ai.core.config import Settings


def test_ticket_is_bounded_single_use_and_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    import noris_ai.chat.tickets as module

    now = 10.0
    monkeypatch.setattr(module.time, "monotonic", lambda: now)
    store = WsTicketStore(ttl_seconds=5, max_outstanding=1)
    first = store.issue()
    with pytest.raises(PermissionError):
        store.issue()
    assert store.redeem(first.id)
    assert not store.redeem(first.id)
    expired = store.issue()
    now = 16
    assert not store.redeem(expired.id)
    assert store.issue().id != expired.id


def test_backpressure_never_grows_queue() -> None:
    peer = Peer(asyncio.Queue(maxsize=2))
    for seq in range(1000):
        peer.offer({"seq": seq})
    assert peer.queue.qsize() == 2
    assert peer.overflow.is_set()


def test_protocol_rejects_wrong_version_history_owner_and_invalid_sequence() -> None:
    adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
    for raw in (
        '{"version":2,"type":"chat.ping"}',
        '{"version":1,"type":"chat.ping","owner_id":"client-controlled"}',
        '{"version":1,"type":"chat.ping","messages":[{"role":"system","content":"admin"}]}',
        '{"version":1,"type":"chat.resume","generationId":"00000000-0000-0000-0000-000000000001","lastReceivedSeq":-1}',
    ):
        with pytest.raises(ValidationError):
            adapter.validate_json(raw)


@pytest.mark.asyncio
async def test_send_timeout_closes_slow_socket_and_detaches(llm_config: Settings) -> None:
    from types import SimpleNamespace
    from typing import cast

    from starlette.websockets import WebSocket

    from noris_ai.api.v1.chat_ws import websocket_chat
    from noris_ai.chat.generation import GenerationManager
    from noris_ai.chat.repository import ChatRepository
    from noris_ai.llm.gateway import LLMGateway

    config = llm_config.model_copy(update={"chat_ws_send_timeout_seconds": 0.01})
    store = WsTicketStore(60)
    manager = GenerationManager(config, cast(ChatRepository, object()), cast(LLMGateway, object()))
    closed: list[int] = []

    async def accept(subprotocol: str) -> None:
        assert subprotocol == "noris-chat.v1"

    async def blocked_send(text: str) -> None:
        assert '"chat.connected"' in text
        await asyncio.Event().wait()

    async def blocked_receive() -> str:
        await asyncio.Event().wait()
        return ""

    async def close(code: int) -> None:
        closed.append(code)

    socket = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                chat_settings=config, chat_tickets=store, chat_generations=manager
            )
        ),
        headers={"origin": "http://localhost:3000", "host": "localhost:3000"},
        url=SimpleNamespace(scheme="ws"),
        scope={"subprotocols": ["noris-chat.v1", "ticket." + store.issue().id]},
        accept=accept,
        send_text=blocked_send,
        receive_text=blocked_receive,
        close=close,
    )
    await asyncio.wait_for(websocket_chat(cast(WebSocket, socket)), 1)
    assert closed == [1013]
    assert not manager.peers
