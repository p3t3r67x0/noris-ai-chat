import asyncio
import json
import logging
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic

import anyio
from sqlalchemy.exc import SQLAlchemyError

from noris_ai.core.config import Settings
from noris_ai.learning.policy import learning_instruction
from noris_ai.llm.catalog import ModelCatalogService
from noris_ai.llm.continuation import ContinuationFilter, continuation_messages, utf16_length
from noris_ai.llm.errors import LLMError
from noris_ai.llm.pricing import estimate_cost
from noris_ai.llm.provider import LLMProvider, ProviderMessage, provider_payload
from noris_ai.llm.reasoning import apply_preference
from noris_ai.llm.schemas import (
    ChatRequest,
    CompletedEvent,
    ConversationTitleRequest,
    ConversationTitleResponse,
    DeltaEvent,
    FailedEvent,
    IncompleteEvent,
    LLMMessage,
    LLMModel,
    PersistedChatRequest,
    StartedEvent,
)
from noris_ai.llm.titles import TitleInstruction, log_title_event, title_source, validate_title
from noris_ai.llm.tokens import TokenCounter
from noris_ai.llm.vision import VisionMessage, supports_images
from noris_ai.research.schemas import (
    ExternalSourceContent,
    GroundedChatRequest,
    ResearchInstruction,
)
from noris_ai.tools.budget import BudgetCoordinator
from noris_ai.tools.cancellation import drain_cleanup
from noris_ai.tools.errors import ToolError
from noris_ai.tools.registry import payload_digest

logger = logging.getLogger(__name__)


class LLMGateway:
    """Bounded, single-worker admission; never silently truncate or automatically retry."""

    def __init__(
        self,
        config: Settings,
        provider: LLMProvider | None,
        budget: BudgetCoordinator | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.budget = budget
        self._durable_phases: set[str] = set()
        self.catalog = ModelCatalogService(config, provider)
        self._estimated_costs: dict[str, Decimal | None] = {}
        self._admitted: dict[str, LLMModel] = {}
        self._active: set[str] = set()
        self._recent: deque[float] = deque()
        self._budget_day = datetime.now(UTC).date()
        self._reserved_tokens = 0
        self._title_attempts: set[str] = set()
        self._counter = TokenCounter(config)
        self._answer_targets: dict[str, tuple[str, str]] = {}
        self._continuation_ids: set[str] = set()
        self._input_ceilings: dict[str, int] = {}

    async def reserve(self, request: ChatRequest, *, input_token_reserve: int = 0) -> None:
        if not 0 <= input_token_reserve <= 12000:
            raise LLMError("CONTEXT_LIMIT", 413)
        model = apply_preference(
            await self.catalog.require(request.modelId), request.reasoningPreference
        )
        self.check_input(request, model)
        target = (request.conversationId, request.assistantMessageId or request.generationId)
        if target in self._answer_targets.values():
            raise LLMError("GENERATION_ACTIVE", 409)
        if request.operation == "continue":
            if request.continuationCount > self.config.llm_max_continuations:
                raise LLMError("CONTINUATION_LIMIT", 400)
            if utf16_length(request.messages[-1].content) >= self.config.llm_max_response_chars:
                raise LLMError("RESPONSE_SIZE_LIMIT", 413)
            if request.generationId in self._continuation_ids:
                raise LLMError("GENERATION_ACTIVE", 409)
            if len(self._continuation_ids) >= 10_000:
                raise LLMError("RATE_LIMIT", 429)
        self._reserve(
            request.generationId,
            model,
            self.provider_messages(request),
            input_token_reserve=input_token_reserve,
        )
        try:
            await self._reserve_durable(
                request.generationId,
                model,
                self.provider_messages(request),
                input_token_reserve=input_token_reserve,
            )
        except BaseException:
            # The ledger may have committed before cancellation reaches this
            # await. Settle that possible reservation, not just the local slot.
            await self.abandon(request.generationId)
            raise
        self._answer_targets[request.generationId] = target
        if request.operation == "continue":
            self._continuation_ids.add(request.generationId)

    async def _reserve_durable(
        self,
        phase: str,
        model: LLMModel,
        messages: Sequence[ProviderMessage],
        *,
        input_token_reserve: int = 0,
    ) -> None:
        if self.budget is None:
            return
        tokens = (
            self._counter.estimate(messages, model.id)
            + model.max_output_tokens
            + model.reasoning_reserve_tokens
            + input_token_reserve
        )
        digest = payload_digest(
            json.dumps(
                {
                    "model": model.id,
                    "messages": [provider_payload(m) for m in messages],
                    "tokens": tokens,
                    "reasoning": model.reasoning_effort,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        )
        self._durable_phases.add(phase)
        try:
            await self.budget.reserve_text(
                self.config.chat_owner_id, phase, digest, tokens, self.config.llm_daily_token_budget
            )
        except ToolError as error:
            raise LLMError(
                "BUDGET_LIMIT" if error.code == "BUDGET_LIMIT" else "GENERATION_ACTIVE",
                error.status,
            ) from None

    async def _dispatch_durable(self, phase: str) -> None:
        if self.budget is not None:
            try:
                await self.budget.dispatch_text(self.config.chat_owner_id, phase)
            except ToolError:
                raise LLMError("GENERATION_ACTIVE", 409) from None

    async def _finish_durable(self, phase: str, *, unknown: bool = False) -> None:
        if self.budget is not None and phase in self._durable_phases:
            try:
                await self.budget.finish_text(self.config.chat_owner_id, phase, unknown=unknown)
            except SQLAlchemyError:
                # The committed ceiling remains charged and startup can recover it.
                # A bookkeeping outage must not discard a received partial answer
                # or strand GenerationManager.live during its terminal cleanup.
                logger.warning("Could not finalize text budget reservation")
            finally:
                self._durable_phases.discard(phase)

    async def abandon(self, phase: str) -> None:
        try:
            await drain_cleanup(asyncio.create_task(self._finish_durable(phase, unknown=True)))
        finally:
            self.release(phase)

    def check_input(self, request: ChatRequest, model: LLMModel) -> None:
        """Side-effect-free admission checks, also used to fit PDF excerpts."""
        for message in request.messages:
            limit = (
                self.config.llm_max_message_chars
                if message.role == "user"
                else self.config.llm_max_response_chars
            )
            if utf16_length(message.content) > limit:
                raise LLMError("REQUEST_TOO_LARGE", 413)
        messages = self.provider_messages(request)
        payload = json.dumps([provider_payload(m) for m in messages], ensure_ascii=False)
        envelope_bytes = (
            2048
            if any(isinstance(m, VisionMessage) for m in messages)
            else 256
            + len(model.id.encode("utf-8"))
            + len((model.reasoning_effort or "").encode("utf-8"))
        )
        if len(payload.encode("utf-8")) + envelope_bytes > self.config.llm_max_request_bytes:
            raise LLMError("REQUEST_TOO_LARGE", 413)
        reservation = (
            self._counter.estimate(messages, model.id)
            + model.max_output_tokens
            + model.reasoning_reserve_tokens
        )
        if reservation > model.context_window:
            raise LLMError("CONTEXT_LIMIT", 413)

    def input_tokens(self, request: ChatRequest, model: LLMModel) -> int:
        return self._counter.estimate(self.provider_messages(request), model.id)

    async def research_capacity(self, request: ChatRequest) -> tuple[LLMModel, int]:
        model = apply_preference(
            await self.catalog.require(request.modelId), request.reasoningPreference
        )
        if not model.research_eligible:
            raise LLMError("MODEL_UNAVAILABLE", 400)
        self.check_input(request, model)
        return model, min(
            12000,
            model.context_window
            - self.input_tokens(request, model)
            - model.max_output_tokens
            - model.reasoning_reserve_tokens,
        )

    def _reserve(
        self,
        generation_id: str,
        model: LLMModel,
        messages: Sequence[ProviderMessage],
        output_limit: int | None = None,
        *,
        input_token_reserve: int = 0,
    ) -> LLMModel:
        if self.provider is None:
            raise LLMError("LLM_DISABLED", 503)
        if any(isinstance(message, VisionMessage) for message in messages):
            if not supports_images(model):
                raise LLMError("MODEL_UNAVAILABLE", 400)
            # Bound the actual inline image request separately from text/context tokens.
            payload = json.dumps([provider_payload(m) for m in messages], ensure_ascii=False)
            if len(payload.encode("utf-8")) + 2048 > self.config.llm_max_request_bytes:
                raise LLMError("REQUEST_TOO_LARGE", 413)
        # UTF-8 byte count is a deliberately conservative bound, not a tokenizer claim.
        if output_limit is not None:
            model = model.model_copy(
                update={"max_output_tokens": min(output_limit, model.max_output_tokens)}
            )
        estimate = self._counter.estimate(messages, model.id)
        reservation = (
            estimate
            + input_token_reserve
            + model.max_output_tokens
            + model.reasoning_reserve_tokens
        )
        if reservation > model.context_window:
            raise LLMError("CONTEXT_LIMIT", 413)
        if generation_id in self._active:
            raise LLMError("GENERATION_ACTIVE", 409)
        now = monotonic()
        while self._recent and self._recent[0] <= now - 60:
            self._recent.popleft()
        if (
            len(self._active) >= self.config.llm_max_concurrent
            or len(self._recent) >= self.config.llm_requests_per_minute
        ):
            raise LLMError("RATE_LIMIT", 429)
        today = datetime.now(UTC).date()
        if today != self._budget_day:
            self._budget_day, self._reserved_tokens = today, 0
        if self._reserved_tokens + reservation > self.config.llm_daily_token_budget:
            raise LLMError("BUDGET_LIMIT", 429)
        self._estimated_costs[generation_id] = estimate_cost(
            model.cost,
            estimate + input_token_reserve,
            model.max_output_tokens + model.reasoning_reserve_tokens,
        )
        self._active.add(generation_id)
        self._admitted[generation_id] = model
        self._input_ceilings[generation_id] = estimate + input_token_reserve
        self._recent.append(now)
        self._reserved_tokens += reservation
        return model

    @staticmethod
    def provider_messages(request: ChatRequest) -> list[ProviderMessage]:
        messages: list[ProviderMessage] = list(continuation_messages(request))
        if isinstance(request, PersistedChatRequest) and request.conversationMode == "learning":
            messages.insert(0, learning_instruction(request.learningState))
        if isinstance(request, GroundedChatRequest):
            messages.insert(0, ResearchInstruction())
            # External content never receives a privileged role and is never
            # interpolated into the fixed instruction or the user's question.
            messages.insert(1, ExternalSourceContent(content=request.research_context))
        return messages

    async def conversation_title(
        self,
        request: ConversationTitleRequest,
        *,
        before_stream: Callable[[], Awaitable[bool]] | None = None,
    ) -> ConversationTitleResponse:
        # REST legacy clients have no durable conversation. Persisted WebSocket
        # chats commit their own atomic claim AFTER admission, BEFORE the call.
        generation_id = "title:" + request.conversationId
        started = monotonic()
        phase = "admission"
        iterator: AsyncIterator[str] | None = None
        admitted = False
        dispatched = False
        succeeded = False

        def diagnostic(outcome: str, code: str | None = None) -> None:
            log_title_event(
                request.conversationId,
                request.modelId,
                phase,
                (monotonic() - started) * 1000,
                outcome,
                code,
            )

        try:
            diagnostic("started")
            provider = self.provider
            if provider is None:
                raise LLMError("LLM_DISABLED", 503)
            if before_stream is None:
                if generation_id in self._title_attempts:
                    raise LLMError("TITLE_ALREADY_ATTEMPTED", 409)
                if len(self._title_attempts) >= 10_000:
                    raise LLMError("RATE_LIMIT", 429)
            messages: list[ProviderMessage] = [
                TitleInstruction(),
                LLMMessage(role="user", content=title_source(request.firstMessage)),
            ]
            model = self._reserve(
                generation_id,
                await self.catalog.require(request.modelId),
                messages,
                self.config.llm_title_max_output_tokens,
            )
            admitted = True
            await self._reserve_durable(generation_id, model, messages)
            if before_stream is not None:
                phase = "claim"
                if not await before_stream():
                    raise LLMError("TITLE_ALREADY_ATTEMPTED", 409)
            else:
                self._title_attempts.add(generation_id)
            phase = "generation"
            diagnostic("started")
            await self._dispatch_durable(generation_id)
            dispatched = True
            iterator = provider.stream(messages, model)
            text = ""
            async with asyncio.timeout(self.config.llm_title_timeout_seconds):
                async for delta in iterator:
                    text += delta
                    if len(text) > 256:
                        raise LLMError("INVALID_RESPONSE")
            phase = "validation"
            result = ConversationTitleResponse(
                conversationId=request.conversationId,
                inputMessageId=request.inputMessageId,
                title=validate_title(text),
            )
            diagnostic("success")
            succeeded = True
            return result
        except TimeoutError:
            diagnostic("failure", "TIMEOUT")
            raise LLMError("TIMEOUT", 504) from None
        except LLMError as error:
            diagnostic(
                "skipped" if error.code == "TITLE_ALREADY_ATTEMPTED" else "failure", error.code
            )
            if error.code in ("MODEL_UNAVAILABLE", "PROVIDER_AUTH_FAILED"):
                self.catalog.invalidate()
            raise
        except asyncio.CancelledError:
            diagnostic("failure", "CANCELLED")
            raise
        except Exception:
            diagnostic("failure", "DATABASE_ERROR" if phase == "claim" else "INTERNAL_ERROR")
            if phase == "claim":
                raise  # The caller isolates DB failures from the completed answer.
            raise LLMError("INTERNAL_ERROR", 500) from None
        finally:
            try:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    await close()
            finally:
                if admitted:
                    with anyio.CancelScope(shield=True):
                        try:
                            await drain_cleanup(
                                asyncio.create_task(
                                    self._finish_durable(
                                        generation_id,
                                        unknown=dispatched and not succeeded,
                                    )
                                )
                            )
                        finally:
                            self.release(generation_id)

    def release(self, generation_id: str) -> None:
        self._active.discard(generation_id)
        self._answer_targets.pop(generation_id, None)
        self._admitted.pop(generation_id, None)
        self._estimated_costs.pop(generation_id, None)
        self._input_ceilings.pop(generation_id, None)

    async def events(
        self,
        request: ChatRequest,
        *,
        before_stream: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncGenerator[
        StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent | None
    ]:
        seq = 1
        started = self._encode(StartedEvent(seq=seq))
        yield StartedEvent(seq=seq)
        provider = self.provider
        if provider is None:
            yield FailedEvent(seq=2, code="LLM_DISABLED", message=LLMError("LLM_DISABLED").message)
            return
        model = self._admitted[request.generationId]
        iterator: AsyncIterator[str] | None = None
        dispatched = False
        succeeded = False
        previous = request.messages[-1].content if request.operation == "continue" else ""
        filter_ = ContinuationFilter(previous)
        text_length = utf16_length(previous)
        has_text = False
        received = len(started)
        pending: asyncio.Future[str] | None = None

        def output(delta: str) -> list[DeltaEvent]:
            nonlocal seq, text_length, has_text, received
            events: list[DeltaEvent] = []
            for offset in range(0, len(delta), 512):
                fragment = delta[offset : offset + 512]
                # Keep all text that fits, including the valid prefix of a boundary chunk.
                available = self.config.llm_max_response_chars - text_length
                if utf16_length(fragment) > available:
                    fragment = fragment.encode("utf-16-le")[: available * 2].decode(
                        "utf-16-le", errors="ignore"
                    )
                if not fragment:
                    break
                encoded = self._encode(DeltaEvent(seq=seq + 1, delta=fragment))
                if received + len(encoded) > self.config.llm_max_stream_bytes - 512:
                    break
                received += len(encoded)
                text_length += utf16_length(fragment)
                has_text = has_text or bool(fragment.strip())
                seq += 1
                events.append(DeltaEvent(seq=seq, delta=fragment))
            return events

        def check_limits(delta: str, before: int) -> None:
            if text_length - before < utf16_length(delta):
                code = (
                    "RESPONSE_SIZE_LIMIT"
                    if text_length >= self.config.llm_max_response_chars - 1
                    else "STREAM_SIZE_LIMIT"
                )
                raise LLMError(code)

        try:
            self.check_input(request, model)
            if (
                request.modelId != model.id
                or self.input_tokens(request, model) > self._input_ceilings[request.generationId]
            ):
                raise LLMError("CONTEXT_LIMIT", 413)
            if (
                isinstance(request, GroundedChatRequest)
                and request.research_deadline_at
                and request.research_deadline_at <= datetime.now(UTC)
            ):
                raise LLMError("TIMEOUT", 504)
            await self._dispatch_durable(request.generationId)
            dispatched = True
            if before_stream is not None:
                await before_stream()
            if (
                isinstance(request, GroundedChatRequest)
                and request.research_deadline_at
                and request.research_deadline_at <= datetime.now(UTC)
            ):
                raise LLMError("TIMEOUT", 504)
            iterator = provider.stream(self.provider_messages(request), model)
            async with asyncio.timeout(
                min(
                    model.timeout_policy.total_seconds,
                    self.config.llm_total_timeout_seconds,
                    max(0, (request.research_deadline_at - datetime.now(UTC)).total_seconds())
                    if isinstance(request, GroundedChatRequest) and request.research_deadline_at
                    else self.config.llm_total_timeout_seconds,
                )
            ):
                while True:
                    pending = asyncio.ensure_future(anext(iterator))
                    while not pending.done():
                        done, _ = await asyncio.wait(
                            {pending}, timeout=self.config.llm_heartbeat_seconds
                        )
                        if not done:
                            heartbeat = b": keepalive\n\n"
                            received += len(heartbeat)
                            if received > self.config.llm_max_stream_bytes - 512:
                                raise LLMError("STREAM_SIZE_LIMIT")
                            yield None
                    try:
                        delta = pending.result()
                    except StopAsyncIteration:
                        break
                    delta = filter_.feed(delta)
                    before = text_length
                    for event in output(delta):
                        yield event
                    check_limits(delta, before)
                delta = filter_.feed("", final=True)
                before = text_length
                for event in output(delta):
                    yield event
                check_limits(delta, before)
            if not has_text:
                raise LLMError("DUPLICATE_CONTINUATION" if previous else "INVALID_RESPONSE")
            succeeded = True
            yield CompletedEvent(seq=seq + 1)
        except (TimeoutError, LLMError) as cause:
            error = cause if isinstance(cause, LLMError) else LLMError("TIMEOUT", 504)
            try:
                delta = filter_.feed("", final=True)
                before = text_length
                for event in output(delta):
                    yield event
                check_limits(delta, before)
            except LLMError as filter_error:
                error = filter_error
            if error.code == "OUTPUT_LIMIT":
                if previous and not has_text:
                    error = LLMError("DUPLICATE_CONTINUATION")
                else:
                    yield IncompleteEvent(seq=seq + 1)
                    return
            if error.code in ("MODEL_UNAVAILABLE", "PROVIDER_AUTH_FAILED"):
                self.catalog.invalidate()
            yield FailedEvent(seq=seq + 1, code=error.code, message=error.message)
        except Exception:
            error = LLMError("INTERNAL_ERROR", 500)
            yield FailedEvent(seq=seq + 1, code=error.code, message=error.message)
        finally:
            # ASGI disconnect uses level cancellation; cleanup must finish even
            # while the response task group is cancelled.
            with anyio.CancelScope(shield=True):
                try:
                    if pending is not None:
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
                    close = getattr(iterator, "aclose", None)
                    if close is not None:
                        await close()
                finally:
                    try:
                        await drain_cleanup(
                            asyncio.create_task(
                                self._finish_durable(
                                    request.generationId,
                                    unknown=dispatched and not succeeded,
                                )
                            )
                        )
                    finally:
                        self.release(request.generationId)

    async def stream(self, request: ChatRequest) -> AsyncGenerator[bytes]:
        iterator = self.events(request)
        try:
            async for event in iterator:
                yield b": keepalive\n\n" if event is None else self._encode(event)
        finally:
            await iterator.aclose()

    @staticmethod
    def _encode(
        event: StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent,
    ) -> bytes:
        return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n".encode()
