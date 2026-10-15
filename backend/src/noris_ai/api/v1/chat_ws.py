"""Authenticated same-origin WebSocket commands and bounded event delivery."""

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import suppress
from typing import Annotated, Literal, cast
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
from noris_ai.chat.ws_protocol import (
    CancelIncomingMessage,
    ClientMessage,
    GenerateIncomingMessage,
    ResumeIncomingMessage,
)
from noris_ai.core.access import security, verify_basic, verify_write_origin
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.tools.errors import ToolError

router = APIRouter(tags=["Chat"])
commands: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
logger = logging.getLogger(__name__)

HandshakeRejection = Literal[
    "ORIGIN_NOT_ALLOWED",
    "HOST_NOT_ALLOWED",
    "INVALID_SCHEME",
    "MISSING_SUBPROTOCOL",
    "MISSING_TICKET_SUBPROTOCOL",
    "MULTIPLE_TICKET_SUBPROTOCOLS",
    "TICKET_INVALID_OR_EXPIRED",
    "CONNECTION_LIMIT",
]


async def _reject_handshake(
    socket: WebSocket, reason: HandshakeRejection, code: int = 1008
) -> None:
    # Only fixed categories reach logs. Even Origin/Host/forwarded headers can
    # contain attacker-supplied secrets, so never echo headers, URLs or protocols.
    scheme = socket.scope.get("scheme")
    forwarded_proto = socket.headers.get("x-forwarded-proto")
    forwarded_category = "missing" if forwarded_proto is None else "invalid"
    if forwarded_proto in ("ws", "wss", "http", "https"):
        forwarded_category = forwarded_proto
    logger.warning(
        "Chat WebSocket handshake rejected: reason=%s scheme=%s forwarded_proto=%s",
        reason,
        scheme if scheme in ("ws", "wss", "http", "https") else "invalid",
        forwarded_category,
        extra={"ws_rejection_reason": reason},
    )
    await socket.close(code=code)


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
    # Retention cleanup may wait on the database. Start the ticket's TTL only
    # afterwards so the response carries a fresh, redeemable ticket.
    await manager.repository.prune_stream_events(config.chat_stream_event_retention_hours)
    store = cast(WsTicketStore, request.app.state.chat_tickets)
    try:
        issued = store.issue()
    except PermissionError:
        raise LLMError("RATE_LIMIT", 429) from None
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
    reason: HandshakeRejection | None = None
    if origin not in config.llm_allowed_origins:
        reason = "ORIGIN_NOT_ALLOWED"
    elif socket.headers.get("host") not in allowed_hosts:
        reason = "HOST_NOT_ALLOWED"
    elif config.environment == "production" and socket.scope.get("scheme") != "wss":
        # Uvicorn maps https -> wss for trusted proxies. Do not independently
        # trust X-Forwarded-Proto here: that would bypass its proxy trust policy.
        reason = "INVALID_SCHEME"
    elif "noris-chat.v1" not in protocols:
        reason = "MISSING_SUBPROTOCOL"
    elif not ticket_protocols:
        reason = "MISSING_TICKET_SUBPROTOCOL"
    elif len(ticket_protocols) != 1:
        reason = "MULTIPLE_TICKET_SUBPROTOCOLS"
    elif not store.redeem(ticket_protocols[0]):
        reason = "TICKET_INVALID_OR_EXPIRED"
    if reason is not None:
        await _reject_handshake(socket, reason)
        return
    manager = cast(GenerationManager, socket.app.state.chat_generations)
    if len(manager.peers) >= 64:
        await _reject_handshake(socket, "CONNECTION_LIMIT", code=1013)
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
                    await manager.resume(
                        peer,
                        command.generationId,
                        command.lastReceivedSeq,
                        command.toolEventVersion,
                        command.toolEventsOnly,
                        research_version=command.researchEventVersion,
                    )
                elif command.type == "chat.cancel":
                    await manager.cancel(command.generationId)
                else:
                    peer.offer({"version": 1, "type": "chat.pong"})
            except (ChatError, LLMError, ToolError) as error:
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.error",
                        "code": error.code,
                        "message": error.message,
                        "requestId": str(command.requestId)
                        if isinstance(command, GenerateIncomingMessage)
                        else str(command.generationId)
                        if isinstance(command, (ResumeIncomingMessage, CancelIncomingMessage))
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
                        else str(command.generationId)
                        if isinstance(command, (ResumeIncomingMessage, CancelIncomingMessage))
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

    async def deliver() -> None:
        # The durable outbox also covers tools committed after chat completion
        # and commits with no local publisher. Reconnect drains the same rows.
        while True:
            await asyncio.sleep(0.1)
            await manager.deliver(peer)

    tasks = [
        asyncio.create_task(receive()),
        asyncio.create_task(send()),
        asyncio.create_task(overflow()),
        asyncio.create_task(deliver()),
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
