"""Authenticated same-origin WebSocket commands and bounded event delivery."""

import asyncio
import json
import time
from collections import deque
from contextlib import suppress
from typing import Annotated, cast
from urllib.parse import urlsplit

import anyio
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBasicCredentials
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from noris_ai.chat.errors import ChatError
from noris_ai.chat.generation import GenerationManager, Peer
from noris_ai.chat.schemas import JsonApiSchema
from noris_ai.chat.tickets import WsTicketStore
from noris_ai.chat.ws_protocol import ClientMessage, GenerateIncomingMessage
from noris_ai.core.access import security, verify_basic, verify_write_origin
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError

router = APIRouter(tags=["Chat"])
commands: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class TicketResponse(JsonApiSchema):
    ticketId: str
    expiresInSeconds: float


@router.post("/chat/ws-ticket", operation_id="createChatWsTicket", response_model=TicketResponse)
async def ticket(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> TicketResponse:
    config = cast(Settings, request.app.state.chat_settings)
    verify_basic(credentials, config)
    verify_write_origin(request, config)
    manager = cast(GenerationManager, request.app.state.chat_generations)
    if len(manager.peers) >= 64:
        raise LLMError("RATE_LIMIT", 429)
    store = cast(WsTicketStore, request.app.state.chat_tickets)
    try:
        issued = store.issue()
    except PermissionError:
        raise LLMError("RATE_LIMIT", 429) from None
    await manager.repository.prune_stream_events(config.chat_stream_event_retention_hours)
    return TicketResponse(ticketId=issued.id, expiresInSeconds=config.chat_ws_ticket_ttl_seconds)


@router.websocket("/chat/ws")
async def websocket_chat(socket: WebSocket) -> None:
    config = cast(Settings, socket.app.state.chat_settings)
    origin = socket.headers.get("origin")
    allowed_hosts = config.chat_ws_allowed_hosts or tuple(
        urlsplit(value).netloc for value in config.llm_allowed_origins
    )
    protocols = socket.scope.get("subprotocols", [])
    ticket_protocols = [p.removeprefix("ticket.") for p in protocols if p.startswith("ticket.")]
    store = cast(WsTicketStore, socket.app.state.chat_tickets)
    if (
        origin not in config.llm_allowed_origins
        or socket.headers.get("host") not in allowed_hosts
        or (config.environment == "production" and socket.url.scheme != "wss")
        or "noris-chat.v1" not in protocols
        or len(ticket_protocols) != 1
        or not store.redeem(ticket_protocols[0])
    ):
        await socket.close(code=1008)
        return
    manager = cast(GenerationManager, socket.app.state.chat_generations)
    if len(manager.peers) >= 64:
        await socket.close(code=1013)
        return
    await socket.accept(subprotocol="noris-chat.v1")
    peer = Peer(asyncio.Queue(maxsize=config.chat_ws_queue_size))
    manager.peers.add(peer)
    peer.offer(
        {
            "version": 1,
            "type": "chat.connected",
            "heartbeatSeconds": config.chat_ws_heartbeat_seconds,
        }
    )
    recent: deque[float] = deque()

    async def receive() -> None:
        while True:
            raw = await socket.receive_text()
            if len(raw.encode("utf-8")) > min(config.llm_max_request_bytes, 262144):
                await socket.close(code=1009)
                return
            now = time.monotonic()
            while recent and recent[0] < now - 60:
                recent.popleft()
            recent.append(now)
            if len(recent) > 120:
                await socket.close(code=1008)
                return
            command: ClientMessage | None = None
            try:
                command = commands.validate_json(raw)
                if isinstance(command, GenerateIncomingMessage):
                    await manager.generate(peer, command)
                elif command.type == "chat.resume":
                    await manager.resume(peer, command.generationId, command.lastReceivedSeq)
                elif command.type == "chat.cancel":
                    await manager.cancel(command.generationId)
                else:
                    peer.offer({"version": 1, "type": "chat.pong"})
            except (ChatError, LLMError) as error:
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.error",
                        "code": error.code,
                        "message": error.message,
                        "requestId": str(command.requestId)
                        if isinstance(command, GenerateIncomingMessage)
                        else None,
                    }
                )
            except (ValidationError, SQLAlchemyError):
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.error",
                        "code": "INVALID_INPUT",
                        "message": "Die Chatanfrage konnte nicht verarbeitet werden.",
                        "requestId": str(command.requestId)
                        if isinstance(command, GenerateIncomingMessage)
                        else None,
                    }
                )

    async def send() -> None:
        while True:
            try:
                event = await asyncio.wait_for(peer.queue.get(), config.chat_ws_heartbeat_seconds)
            except TimeoutError:
                event = {"version": 1, "type": "chat.heartbeat"}
            encoded = json.dumps(event, ensure_ascii=True)
            if len(encoded) > 8_388_608:
                await socket.close(code=1009)
                return
            await asyncio.wait_for(socket.send_text(encoded), config.chat_ws_send_timeout_seconds)

    async def overflow() -> None:
        await peer.overflow.wait()

    tasks = [
        asyncio.create_task(receive()),
        asyncio.create_task(send()),
        asyncio.create_task(overflow()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        with anyio.CancelScope(shield=True):
            manager.detach(peer)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with suppress(RuntimeError, WebSocketDisconnect):
                await socket.close(code=1013)
