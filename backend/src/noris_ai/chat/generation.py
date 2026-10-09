"""Bounded generation lifecycle, independent of any browser socket.

The existing LLMGateway supplies the only provider path and all admission
limits. Each delivered batch has already committed together with its answer
snapshot. This process owns one worker; replicas require distributed admission.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import ValidationError

from noris_ai.chat.errors import ChatError
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.service import ChatService, conversation_response, message_response
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import (
    ChatRequest,
    CompletedEvent,
    ConversationTitleRequest,
    DeltaEvent,
    FailedEvent,
    IncompleteEvent,
    LLMMessage,
    StartedEvent,
)

type Payload = dict[str, object]
logger = logging.getLogger(__name__)


@dataclass(eq=False)
class Peer:
    queue: asyncio.Queue[Payload]
    overflow: asyncio.Event = field(default_factory=asyncio.Event)

    def offer(self, event: Payload) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.overflow.set()


@dataclass
class LiveGeneration:
    command: GenerateIncomingMessage
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    peers: set[Peer] = field(default_factory=lambda: set[Peer]())
    detached_at: float | None = None
    task: asyncio.Task[None] | None = None
    interruption: bool = False
    cancellation_requested: bool = False
    started: bool = False


class GenerationManager:
    def __init__(self, config: Settings, repository: ChatRepository, gateway: LLMGateway) -> None:
        self.config, self.repository, self.gateway = config, repository, gateway
        self.live: dict[UUID, LiveGeneration] = {}
        self.admission = asyncio.Lock()
        self.peers: set[Peer] = set()
        self.tasks: set[asyncio.Task[None]] = set()

    def broadcast(self, event: Payload) -> None:
        for peer in self.peers:
            peer.offer(event)

    def detach(self, peer: Peer) -> None:
        self.peers.discard(peer)
        for live in self.live.values():
            live.peers.discard(peer)
            if not live.peers and live.detached_at is None:
                live.detached_at = time.monotonic()

    async def generate(self, peer: Peer, command: GenerateIncomingMessage) -> None:
        async with self.admission:
            if (
                len(self.live) >= self.config.llm_max_concurrent
                and command.requestId not in self.live
            ):
                raise LLMError("RATE_LIMIT", 429)
            if not command.content.strip():
                raise ChatError("INVALID_INPUT", 422)
            generation, path, created = await self.repository.begin_generation(
                self.config.chat_owner_id, command
            )
            if created:
                live = LiveGeneration(command, peers={peer})
                self.live[generation.id] = live
                input_message = next(m for m in path if m.id == command.inputMessageId)
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.message.created",
                        "conversationId": str(command.conversationId),
                        "message": message_response(input_message).model_dump(mode="json"),
                    }
                )
                try:
                    request = ChatRequest(
                        generationId=str(generation.id),
                        conversationId=str(command.conversationId),
                        inputMessageId=str(command.inputMessageId),
                        modelId=command.modelId,
                        messages=[LLMMessage(role=m.role, content=m.content) for m in path],  # type: ignore[arg-type]
                        attempt=command.attempt,
                        operation=command.operation,
                        assistantMessageId=str(command.assistantMessageId)
                        if command.operation == "continue"
                        else None,
                        continuationCount=path[-1].continuation_count + 1
                        if command.operation == "continue"
                        else 0,
                    )
                except ValidationError:
                    self.live.pop(generation.id, None)
                    error = LLMError("INVALID_REQUEST")
                    payload: Payload = {
                        "version": 1,
                        "type": "chat.generation.failed",
                        "generationId": str(generation.id),
                        "conversationId": str(command.conversationId),
                        "messageId": str(command.assistantMessageId),
                        "seq": 1,
                        "content": path[-1].content if command.operation == "continue" else "",
                        "code": error.code,
                        "message": error.message,
                    }
                    await self.repository.persist_generation_event(
                        generation.id, payload, str(payload["content"]), "failed", error.code
                    )
                    peer.offer(payload)
                    return
                live.task = asyncio.create_task(self._run(live, request))
                self.tasks.add(live.task)
                live.task.add_done_callback(self.task_finished)
            else:
                await self.resume(peer, command.requestId, 0)

    def task_finished(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("Chat generation persistence or cleanup failed")

    async def cancel_conversation(self, conversation_id: UUID) -> None:
        for generation_id, live in list(self.live.items()):
            if live.command.conversationId == conversation_id:
                await self.cancel(generation_id)

    async def resume(self, peer: Peer, generation_id: UUID, last_sequence: int) -> None:
        live = self.live.get(generation_id)
        # Writer and subscription share a lock: replay cannot race a live delta.
        async with live.lock if live is not None else asyncio.Lock():
            generation = await self.repository.get_generation(
                self.config.chat_owner_id, generation_id
            )
            await self.repository.get_conversation(
                self.config.chat_owner_id, generation.conversation_id
            )
            if last_sequence > generation.last_sequence:
                raise ChatError("INVALID_INPUT", 422)
            events = await self.repository.list_stream_events(
                generation_id, after_sequence=last_sequence
            )
            peer.offer(
                {
                    "version": 1,
                    "type": "chat.resume.accepted",
                    "generationId": str(generation_id),
                    "lastReceivedSeq": last_sequence,
                }
            )
            capacity = peer.queue.maxsize - peer.queue.qsize() - 2
            contiguous = (
                events
                and events[0].sequence == last_sequence + 1
                and events[-1].sequence == generation.last_sequence
            )
            if contiguous and len(events) <= capacity and generation.operation != "continue":
                for event in events:
                    peer.offer(event.payload)
            else:
                message = await self.repository.get_message(
                    self.config.chat_owner_id,
                    generation.conversation_id,
                    generation.assistant_message_id,  # type: ignore[arg-type]
                )
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.resume.snapshot",
                        "generationId": str(generation_id),
                        "conversationId": str(generation.conversation_id),
                        "messageId": str(message.id),
                        "content": message.content,
                        "status": generation.status,
                        "lastSequence": generation.last_sequence,
                    }
                )
            if live is not None:
                live.peers.add(peer)
                live.detached_at = None

    async def cancel(self, generation_id: UUID) -> None:
        generation = await self.repository.get_generation(self.config.chat_owner_id, generation_id)
        await self.repository.get_conversation(
            self.config.chat_owner_id, generation.conversation_id
        )
        live = self.live.get(generation_id)
        if live is not None and live.task is not None:
            live.cancellation_requested = True
            if live.started:
                live.task.cancel()

    async def close(self) -> None:
        tasks: list[asyncio.Task[None]] = list(self.tasks)
        for live in list(self.live.values()):
            live.interruption = True
            if live.task is not None:
                live.task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, live: LiveGeneration, request: ChatRequest) -> None:
        live.started = True
        command = live.command
        sequence, content, buffered = (
            0,
            request.messages[-1].content if request.operation == "continue" else "",
            "",
        )
        terminal, error_code = "completed", None
        last_flush = time.monotonic()
        iterator = self.gateway.events(request)
        pending: (
            asyncio.Task[
                StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent | None
            ]
            | None
        ) = None

        async def emit(kind: str, delta: str = "", status: str = "running") -> None:
            nonlocal sequence
            payload: Payload = {
                "version": 1,
                "type": "chat.generation." + kind,
                "generationId": str(command.requestId),
                "conversationId": str(command.conversationId),
                "messageId": str(command.assistantMessageId),
                "seq": sequence + 1,
            }
            if kind == "started":
                payload["modelId"] = command.modelId
            elif kind == "delta":
                payload["delta"] = delta
            else:
                payload["content"] = content
                if kind == "failed":
                    error = LLMError(error_code or "INTERNAL_ERROR")
                    payload.update(code=error.code, message=error.message)
                if kind == "incomplete":
                    payload["reason"] = "output_limit"
            async with live.lock:
                await self.repository.persist_generation_event(
                    command.requestId, payload, content, status, error_code
                )
                sequence += 1
                for peer in live.peers:
                    peer.offer(payload)

        try:
            if live.cancellation_requested:
                raise asyncio.CancelledError
            await self.gateway.reserve(request)
            await emit("started")
            conversation = await self.repository.get_conversation(
                self.config.chat_owner_id, command.conversationId
            )
            self.broadcast(
                {
                    "version": 1,
                    "type": "chat.conversation.updated",
                    "conversation": conversation_response(conversation).model_dump(mode="json"),
                }
            )
            while True:
                if pending is None:
                    pending = asyncio.create_task(anext(iterator))
                interval = self.config.chat_stream_flush_ms / 1000
                wait_seconds = (
                    max(0.001, interval - (time.monotonic() - last_flush)) if buffered else interval
                )
                done, _ = await asyncio.wait({pending}, timeout=wait_seconds)
                if (
                    live.detached_at is not None
                    and time.monotonic() - live.detached_at
                    >= self.config.chat_disconnect_grace_seconds
                ):
                    live.interruption = True
                    raise asyncio.CancelledError
                if done:
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        break
                    pending = None
                    if event is not None:
                        if event.type == "response.output_text.delta":
                            buffered += event.delta
                            content += event.delta
                        elif event.type == "response.failed":
                            terminal, error_code = "failed", event.code
                        elif event.type == "response.incomplete":
                            terminal = "incomplete"
                if buffered and (
                    time.monotonic() - last_flush >= interval
                    or len(buffered) >= self.config.chat_stream_flush_characters
                ):
                    await emit("delta", buffered)
                    buffered = ""
                    last_flush = time.monotonic()
        except asyncio.CancelledError:
            terminal = "interrupted" if live.interruption else "cancelled"
        except LLMError as error:
            terminal, error_code = "failed", error.code
        except Exception:
            terminal, error_code = "failed", "INTERNAL_ERROR"
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()
            self.gateway.release(request.generationId)
            try:
                if buffered:
                    await emit("delta", buffered)
                await emit(terminal, status=terminal)
            finally:
                self.live.pop(command.requestId, None)
        if (
            terminal == "completed"
            and command.operation == "generate"
            and command.parentMessageId is None
        ):
            try:
                title = await self.gateway.conversation_title(
                    ConversationTitleRequest(
                        conversationId=str(command.conversationId),
                        inputMessageId=str(command.inputMessageId),
                        modelId=command.modelId,
                        firstMessage=command.content[:1024],
                    )
                )
                conversation_result = await ChatService(self.repository).apply_generated_title(
                    self.config.chat_owner_id, command.conversationId, title.title
                )
                if conversation_result is not None:
                    self.broadcast(
                        {
                            "version": 1,
                            "type": "chat.title.updated",
                            "conversationId": str(command.conversationId),
                            "title": conversation_result.title,
                            "titleSource": conversation_result.titleSource,
                        }
                    )
                    self.broadcast(
                        {
                            "version": 1,
                            "type": "chat.conversation.updated",
                            "conversation": conversation_result.model_dump(mode="json"),
                        }
                    )
            except (LLMError, ChatError):
                pass  # Title failure never changes an answer's terminal state.
