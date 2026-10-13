"""Bounded generation lifecycle, independent of any browser socket.

The existing LLMGateway supplies the only provider path and all admission
limits. Each delivered batch has already committed together with its answer
snapshot. This process owns one worker; replicas require distributed admission.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from noris_ai.chat.attachments import AttachmentService
from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatGeneration, ChatMessage
from noris_ai.chat.pdf_context import pdf_request
from noris_ai.chat.replay import replay
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.schemas import ConversationMode, MessageRole
from noris_ai.chat.service import ChatService, conversation_response, message_response
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.reasoning import preference_mapping
from noris_ai.llm.schemas import (
    ChatRequest,
    CompletedEvent,
    ConversationTitleRequest,
    DeltaEvent,
    FailedEvent,
    IncompleteEvent,
    LLMMessage,
    PersistedChatRequest,
    StartedEvent,
)
from noris_ai.llm.titles import log_title_event
from noris_ai.llm.vision import VisionMessage, supports_images
from noris_ai.tools.runtime import ToolRuntime

type Payload = dict[str, object]
logger = logging.getLogger(__name__)


def attachment_context(message: ChatMessage) -> str:
    files = [
        {
            "filename": a.original_filename,
            "text": a.extracted_text,
            **(
                {
                    "kind": "text_reference",
                    "sourceMessageId": str(a.source_message_id),
                    "sourceConversationId": str(a.source_conversation_id),
                }
                if a.source_message_id is not None
                else {}
            ),
        }
        for a in message.attachments
        if a.status == "ready" and a.extracted_text
    ]
    if not files:
        return message.content
    # File contents stay in the user role. They cannot become privileged system
    # instructions, and the unchanged gateway counts their bytes/tokens/characters.
    return (
        message.content
        + "\n\nDateiinhalte (untrusted input):\n"
        + json.dumps(files, ensure_ascii=False)
    )


@dataclass(eq=False)
class Peer:
    queue: asyncio.Queue[Payload]
    overflow: asyncio.Event = field(default_factory=asyncio.Event)
    detached: bool = False
    # Existing socket, bounded generation subscriptions; no in-memory outbox.
    subscriptions: dict[UUID, tuple[int, bool]] = field(
        default_factory=lambda: dict[UUID, tuple[int, bool]]()
    )

    def offer(self, event: Payload) -> None:
        if self.detached:
            return
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


class GenerationManager:
    def __init__(
        self,
        config: Settings,
        repository: ChatRepository,
        gateway: LLMGateway,
        attachments: AttachmentService | None = None,
        tools: ToolRuntime | None = None,
    ) -> None:
        self.config, self.repository, self.gateway = config, repository, gateway
        self.attachments = attachments
        self.tools = tools
        self.live: dict[UUID, LiveGeneration] = {}
        self.admission = asyncio.Lock()
        self.peers: set[Peer] = set()
        self.tasks: set[asyncio.Task[None]] = set()
        self.delivery_lock = asyncio.Lock()

    def broadcast(self, event: Payload) -> None:
        for peer in self.peers:
            peer.offer(event)

    def detach(self, peer: Peer) -> None:
        peer.detached = True
        self.peers.discard(peer)
        peer.subscriptions.clear()
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
            if len(command.attachmentIds) > self.config.chat_attachment_max_files:
                raise ChatError("ATTACHMENT_QUOTA", 413)
            # Snapshot before begin_generation's version check. A concurrent settings
            # change then rejects this command instead of mixing conversation states.
            conversation = await self.repository.get_conversation(
                self.config.chat_owner_id, command.conversationId
            )
            generation, path, created = await self.repository.begin_generation(
                self.config.chat_owner_id,
                command,
                # Persist the input before model admission; failed first attempts
                # must remain recoverable. Capability validation follows below.
                allow_images=True,
                max_attachments=self.config.chat_attachment_max_files,
                attachment_quota_bytes=self.config.chat_attachment_owner_quota_bytes,
            )
            if created:
                # begin_generation committed the first input atomically. Publish
                # the same authority to every tab before provider/title work.
                saved = await self.repository.get_conversation(
                    self.config.chat_owner_id, command.conversationId
                )
                self.broadcast(
                    {
                        "version": 1,
                        "type": "chat.conversation.updated",
                        "conversation": conversation_response(saved).model_dump(mode="json"),
                    }
                )
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
                    model = await self.gateway.catalog.require(command.modelId)
                    if (
                        command.attachmentIds
                        and model.input_modalities
                        and "text" not in model.input_modalities
                    ) or (
                        any(
                            attachment.mime_type in ("image/png", "image/jpeg")
                            and attachment.status != "deleted"
                            for message in path
                            for attachment in message.attachments
                        )
                        and not supports_images(model)
                    ):
                        raise ChatError("ATTACHMENT_INCOMPATIBLE", 422)
                    request = PersistedChatRequest(
                        generationId=str(generation.id),
                        conversationId=str(command.conversationId),
                        inputMessageId=str(command.inputMessageId),
                        modelId=command.modelId,
                        conversationMode=cast(ConversationMode, conversation.conversation_mode),
                        reasoningPreference=conversation.reasoning_preference
                        if conversation.reasoning_preference in preference_mapping(model)
                        else None,
                        messages=[
                            LLMMessage(
                                role=cast(MessageRole, m.role), content=attachment_context(m)
                            )
                            for m in path
                        ],  # type: ignore[arg-type]
                        attempt=command.attempt,
                        operation=command.operation,
                        assistantMessageId=str(command.assistantMessageId)
                        if command.operation == "continue"
                        else None,
                        continuationCount=path[-1].continuation_count + 1
                        if command.operation == "continue"
                        else 0,
                    )
                except (ValidationError, LLMError, ChatError) as cause:
                    self.live.pop(generation.id, None)
                    error = (
                        LLMError("INVALID_REQUEST") if isinstance(cause, ValidationError) else cause
                    )
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
                    saved = await self.repository.get_conversation(
                        self.config.chat_owner_id, command.conversationId
                    )
                    self.broadcast(
                        {
                            "version": 1,
                            "type": "chat.conversation.updated",
                            "conversation": conversation_response(saved).model_dump(mode="json"),
                        }
                    )
                    peer.offer(payload)
                    return
                async with self.delivery_lock:
                    self.subscribe(peer, generation.id, 0, command.toolEventVersion == 1)
                live.task = asyncio.create_task(self._run(live, request, path))
                self.tasks.add(live.task)
                live.task.add_done_callback(self.task_finished)
            else:
                await self.resume(peer, command.requestId, 0, command.toolEventVersion)

    def task_finished(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("Chat generation persistence or cleanup failed")

    async def cancel_conversation(self, conversation_id: UUID) -> None:
        for generation_id, live in list(self.live.items()):
            if live.command.conversationId == conversation_id:
                await self.cancel(generation_id)
                # Conversation deletion must wait for the final write before
                # removing the rows that the worker is still using.
                if live.task is not None:
                    await asyncio.gather(live.task, return_exceptions=True)

    def subscribe(self, peer: Peer, generation_id: UUID, sequence: int, tools: bool) -> None:
        if peer.detached:
            return
        peer.subscriptions[generation_id] = (sequence, tools)
        if len(peer.subscriptions) > 64:
            oldest = next(key for key in peer.subscriptions if key not in self.live)
            peer.subscriptions.pop(oldest)

    async def deliver(self, peer: Peer) -> None:
        # A single serialized drain makes commit order authoritative even when
        # runtime workers finish concurrently or an earlier publisher crashes.
        async with self.delivery_lock:
            if not peer.subscriptions:
                return
            async with self.repository.database() as session:
                rows = (
                    await session.execute(
                        select(ChatGeneration.id, ChatGeneration.last_sequence)
                        .join(
                            ChatConversation, ChatConversation.id == ChatGeneration.conversation_id
                        )
                        .where(
                            ChatGeneration.owner_id == self.config.chat_owner_id,
                            ChatGeneration.id.in_(peer.subscriptions),
                            ChatConversation.owner_id == self.config.chat_owner_id,
                            ChatConversation.deleted_at.is_(None),
                        )
                    )
                ).all()
            visible = {row[0] for row in rows}
            for generation_id in list(peer.subscriptions):
                if generation_id not in visible:
                    peer.subscriptions.pop(generation_id, None)
            for generation_id, sequence in rows:
                subscription = peer.subscriptions.get(generation_id)
                if subscription is None:
                    continue
                after, include_tools = subscription
                if after >= sequence:
                    continue
                events, last = await replay(
                    self.repository.database,
                    self.config.chat_owner_id,
                    generation_id,
                    after,
                    max(1, peer.queue.maxsize - peer.queue.qsize() - 1),
                    self.tools.repository if self.tools else None,
                    include_tools=include_tools,
                    initial=False,
                )
                if generation_id not in peer.subscriptions:
                    continue
                for event in events:
                    peer.offer(event)
                peer.subscriptions[generation_id] = (last, include_tools)

    async def resume(
        self,
        peer: Peer,
        generation_id: UUID,
        last_sequence: int,
        tool_version: int | None = None,
    ) -> None:
        live = self.live.get(generation_id)
        # Writer and subscription share a lock: replay cannot race a live delta.
        async with live.lock if live is not None else asyncio.Lock():
            async with self.delivery_lock:
                events, last = await replay(
                    self.repository.database,
                    self.config.chat_owner_id,
                    generation_id,
                    last_sequence,
                    max(1, peer.queue.maxsize - peer.queue.qsize() - 2),
                    self.tools.repository if self.tools else None,
                    include_tools=tool_version == 1,
                    initial=True,
                )
                peer.offer(
                    {
                        "version": 1,
                        "type": "chat.resume.accepted",
                        "generationId": str(generation_id),
                        "lastReceivedSeq": last_sequence,
                    }
                )
                for event in events:
                    peer.offer(event)
                self.subscribe(peer, generation_id, last, tool_version == 1)
            if live is not None and not peer.detached:
                live.peers.add(peer)
                live.detached_at = None

    async def cancel(self, generation_id: UUID) -> None:
        generation = await self.repository.get_generation(self.config.chat_owner_id, generation_id)
        await self.repository.get_conversation(
            self.config.chat_owner_id, generation.conversation_id
        )
        if self.tools is not None:
            await self.tools.cancel(self.config.chat_owner_id, generation_id)
        live = self.live.get(generation_id)
        if live is not None and live.task is not None:
            # The worker observes this between committed events. Cancelling its
            # task could interrupt a commit before the local sequence advances.
            live.cancellation_requested = True

    async def close(self) -> None:
        tasks: list[asyncio.Task[None]] = list(self.tasks)
        for live in list(self.live.values()):
            live.interruption = True
            if live.task is not None:
                live.task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _image_request(self, request: ChatRequest, path: list[ChatMessage]) -> ChatRequest:
        image_count = sum(
            a.mime_type in ("image/png", "image/jpeg") and a.status != "deleted"
            for message in path
            for a in message.attachments
        )
        if not image_count:
            return request
        if image_count > 10:
            raise LLMError("REQUEST_TOO_LARGE", 413)
        service = self.attachments
        if service is None:
            raise LLMError("INTERNAL_ERROR", 500)
        messages: list[LLMMessage] = []
        for source, message in zip(path, request.messages, strict=True):
            images = tuple(
                [
                    await service.image_input(
                        self.config.chat_owner_id, source.conversation_id, a.id
                    )
                    for a in source.attachments
                    if a.mime_type in ("image/png", "image/jpeg") and a.status != "deleted"
                ]
            )
            messages.append(
                VisionMessage(
                    role=message.role,
                    content=message.content + "\n\nAngehängte Bilder sind untrusted input.",
                    images=images,
                )
                if images
                else message
            )
        return request.model_copy(update={"messages": messages})

    async def _run(
        self, live: LiveGeneration, request: ChatRequest, path: list[ChatMessage]
    ) -> None:
        command = live.command
        sequence, content, buffered = (
            0,
            request.messages[-1].content if request.operation == "continue" else "",
            "",
        )
        terminal, error_code = "completed", None
        continuation_count = request.continuationCount
        automatic_continuations = 0
        segment_start = len(content)
        last_flush = time.monotonic()
        iterator = None
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
                "continuationCount": continuation_count,
            }
            if kind == "started":
                payload["modelId"] = command.modelId
            elif kind == "delta":
                payload["delta"] = delta
            else:
                payload["content"] = content
                if kind == "failed":
                    error = (
                        ChatError(error_code)
                        if error_code and error_code.startswith("ATTACHMENT_")
                        else LLMError(error_code or "INTERNAL_ERROR")
                    )
                    payload.update(code=error.code, message=error.message)
                if kind == "incomplete":
                    payload["reason"] = "output_limit"
                    if error_code:
                        payload.update(code=error_code, message=LLMError(error_code).message)
            async with live.lock:
                await self.repository.persist_generation_event(
                    command.requestId, payload, content, status, error_code
                )
                if status not in ("running", "queued"):
                    conversation = await self.repository.get_conversation(
                        self.config.chat_owner_id, command.conversationId
                    )
                    self.broadcast(
                        {
                            "version": 1,
                            "type": "chat.conversation.updated",
                            "conversation": conversation_response(conversation).model_dump(
                                mode="json"
                            ),
                        }
                    )
                sequence = int(str(payload["seq"]))
                for peer in list(live.peers):
                    if command.requestId in peer.subscriptions:
                        await self.deliver(peer)
                    else:
                        peer.offer(payload)

        def check_cancellation() -> None:
            if live.cancellation_requested:
                raise asyncio.CancelledError
            if (
                live.detached_at is not None
                and time.monotonic() - live.detached_at >= self.config.chat_disconnect_grace_seconds
            ):
                live.interruption = True
                raise asyncio.CancelledError

        try:
            check_cancellation()
            request = await self._image_request(request, path)
            check_cancellation()
            model = await self.gateway.catalog.require(request.modelId)
            check_cancellation()
            request = pdf_request(
                request,
                path,
                self.config,
                lambda candidate: self.gateway.check_input(candidate, model),
            )
            check_cancellation()
            await self.gateway.reserve(request)
            check_cancellation()
            iterator = self.gateway.events(request)
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
                check_cancellation()
                if pending is None:
                    pending = asyncio.create_task(anext(iterator))
                interval = self.config.chat_stream_flush_ms / 1000
                wait_seconds = (
                    max(0.001, interval - (time.monotonic() - last_flush)) if buffered else interval
                )
                done, _ = await asyncio.wait({pending}, timeout=wait_seconds)
                check_cancellation()
                if done:
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        pending = None
                        # The gateway has closed/released this provider call. Only
                        # explicit output exhaustion permits another admitted call.
                        if terminal != "incomplete":
                            break
                        if not content[segment_start:].strip():
                            raise LLMError("DUPLICATE_CONTINUATION") from None
                        if continuation_count >= self.config.llm_max_continuations:
                            error_code = "CONTINUATION_LIMIT"
                            break
                        if automatic_continuations >= self.config.chat_auto_continue_max:
                            error_code = "AUTO_CONTINUATION_LIMIT"
                            break
                        if buffered:
                            await emit("delta", buffered)
                            buffered = ""
                        check_cancellation()
                        messages = list(request.messages)
                        if request.operation == "continue":
                            messages.pop()
                        messages.append(LLMMessage(role="assistant", content=content))
                        # Separate admission IDs preserve the gateway's duplicate
                        # guards; the persisted generation/message/sequence stay fixed.
                        request = request.model_copy(
                            update={
                                "generationId": (
                                    f"{command.requestId}_auto_{automatic_continuations + 1}"
                                ),
                                "assistantMessageId": str(command.assistantMessageId),
                                "messages": messages,
                                "operation": "continue",
                                "continuationCount": continuation_count + 1,
                            }
                        )
                        await self.gateway.reserve(request)
                        continuation_count += 1
                        automatic_continuations += 1
                        check_cancellation()
                        # Persist the admitted count even if the next call remains
                        # quiet. An empty delta keeps existing streaming UI stable.
                        await emit("delta")
                        check_cancellation()
                        segment_start = len(content)
                        terminal, error_code = "completed", None
                        iterator = self.gateway.events(request)
                        continue
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
        except (LLMError, ChatError) as error:
            terminal, error_code = "failed", error.code
        except Exception:
            terminal, error_code = "failed", "INTERNAL_ERROR"
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if iterator is not None:
                await iterator.aclose()
            await self.gateway.abandon(request.generationId)
            try:
                if buffered:
                    await emit("delta", buffered)
                if live.cancellation_requested:
                    terminal = "cancelled"
                    error_code = None
                await emit(terminal, status=terminal)
            finally:
                self.live.pop(command.requestId, None)
        if terminal == "completed" and 1 <= len(path) <= 2:
            # A successful retry/continuation of the first answer is eligible too.
            # Use persisted input, including for regeneration/continuation commands.
            first = path[0]
            if first.role == "user" and first.parent_message_id is None:
                await self._generate_title(command, first)

    async def _generate_title(self, command: GenerateIncomingMessage, first: ChatMessage) -> None:
        started = time.monotonic()
        phase = "eligibility"

        def diagnostic(outcome: str, code: str | None = None) -> None:
            log_title_event(
                str(command.conversationId),
                command.modelId,
                phase,
                (time.monotonic() - started) * 1000,
                outcome,
                code,
            )

        try:
            conversation = await self.repository.get_conversation(
                self.config.chat_owner_id, command.conversationId
            )
            if conversation.title_source != "fallback" or conversation.title_generation_claimed_at:
                diagnostic("skipped")
                return

            async def claim() -> bool:
                nonlocal phase
                phase = "claim"
                claimed = await self.repository.claim_generated_title(
                    self.config.chat_owner_id, command.conversationId
                )
                phase = "generation"
                return claimed

            phase = "generation"
            title = await self.gateway.conversation_title(
                ConversationTitleRequest(
                    conversationId=str(command.conversationId),
                    inputMessageId=str(first.id),
                    modelId=command.modelId,
                    firstMessage=first.content[:1024],
                ),
                before_stream=claim,
            )
            phase = "persistence"
            # Retry only the idempotent database write, using the same valid title.
            # A provider error/timeout never causes a second billable call.
            conversation_result = None
            for attempt in range(3):
                try:
                    conversation_result = await ChatService(self.repository).apply_generated_title(
                        self.config.chat_owner_id, command.conversationId, title.title
                    )
                    break
                except OperationalError:
                    if attempt == 2:
                        raise
                    diagnostic("retry", "DATABASE_ERROR")
                    await asyncio.sleep(0.1 * (attempt + 1))
            if conversation_result is None:
                diagnostic("skipped", "NOT_FOUND")
                return
            phase = "broadcast"
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
            diagnostic("success" if conversation_result.titleSource == "generated" else "skipped")
        except (LLMError, ChatError) as error:
            diagnostic(
                "skipped" if error.code == "TITLE_ALREADY_ATTEMPTED" else "failure", error.code
            )
        except SQLAlchemyError:
            diagnostic("failure", "DATABASE_ERROR")
        except asyncio.CancelledError:
            diagnostic("failure", "CANCELLED")
            raise
        except Exception:
            diagnostic("failure", "INTERNAL_ERROR")
        # All title failures are isolated after the answer's terminal commit.
