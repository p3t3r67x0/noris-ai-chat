import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic

import anyio

from noris_ai.core.config import Settings
from noris_ai.llm.catalog import ModelCatalogService
from noris_ai.llm.continuation import ContinuationFilter, continuation_messages, utf16_length
from noris_ai.llm.errors import LLMError
from noris_ai.llm.pricing import estimate_cost
from noris_ai.llm.provider import LLMProvider, ProviderMessage
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
    StartedEvent,
)
from noris_ai.llm.titles import TitleInstruction, title_source, validate_title
from noris_ai.llm.tokens import TokenCounter


class LLMGateway:
    """Bounded, single-worker admission; never silently truncate or automatically retry."""

    def __init__(self, config: Settings, provider: LLMProvider | None) -> None:
        self.config = config
        self.provider = provider
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

    async def reserve(self, request: ChatRequest) -> None:
        for message in request.messages:
            limit = (
                self.config.llm_max_message_chars
                if message.role == "user"
                else self.config.llm_max_response_chars
            )
            if utf16_length(message.content) > limit:
                raise LLMError("REQUEST_TOO_LARGE", 413)
        model = await self.catalog.require(request.modelId)
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
        self._reserve(request.generationId, model, continuation_messages(request))
        self._answer_targets[request.generationId] = target
        if request.operation == "continue":
            self._continuation_ids.add(request.generationId)

    def _reserve(
        self,
        generation_id: str,
        model: LLMModel,
        messages: Sequence[ProviderMessage],
        output_limit: int | None = None,
    ) -> LLMModel:
        if self.provider is None:
            raise LLMError("LLM_DISABLED", 503)
        # UTF-8 byte count is a deliberately conservative bound, not a tokenizer claim.
        if output_limit is not None:
            model = model.model_copy(
                update={"max_output_tokens": min(output_limit, model.max_output_tokens)}
            )
        estimate = self._counter.estimate(messages, model.id)
        reservation = estimate + model.max_output_tokens + model.reasoning_reserve_tokens
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
            model.cost, estimate, model.max_output_tokens + model.reasoning_reserve_tokens
        )
        self._active.add(generation_id)
        self._admitted[generation_id] = model
        self._recent.append(now)
        self._reserved_tokens += reservation
        return model

    async def conversation_title(
        self, request: ConversationTitleRequest
    ) -> ConversationTitleResponse:
        provider = self.provider
        if provider is None:
            raise LLMError("LLM_DISABLED", 503)
        generation_id = "title:" + request.conversationId
        # Bound duplicate tracking without evicting entries and admitting repeats.
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
        self._title_attempts.add(generation_id)
        iterator: AsyncIterator[str] | None = None
        try:
            iterator = provider.stream(messages, model)
            text = ""
            async with asyncio.timeout(self.config.llm_title_timeout_seconds):
                async for delta in iterator:
                    text += delta
                    if len(text) > 256:
                        raise LLMError("INVALID_RESPONSE")
            return ConversationTitleResponse(
                conversationId=request.conversationId,
                inputMessageId=request.inputMessageId,
                title=validate_title(text),
            )
        except TimeoutError:
            raise LLMError("TIMEOUT", 504) from None
        except LLMError as error:
            if error.code in ("MODEL_UNAVAILABLE", "PROVIDER_AUTH_FAILED"):
                self.catalog.invalidate()
            raise
        except Exception:
            raise LLMError("INTERNAL_ERROR", 500) from None
        finally:
            try:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    await close()
            finally:
                self.release(generation_id)

    def release(self, generation_id: str) -> None:
        self._active.discard(generation_id)
        self._answer_targets.pop(generation_id, None)
        self._admitted.pop(generation_id, None)
        self._estimated_costs.pop(generation_id, None)

    async def events(
        self, request: ChatRequest
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
        iterator = provider.stream(continuation_messages(request), model)
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
            async with asyncio.timeout(
                min(model.timeout_policy.total_seconds, self.config.llm_total_timeout_seconds)
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
