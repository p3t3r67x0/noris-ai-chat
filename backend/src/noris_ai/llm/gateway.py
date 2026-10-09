import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime
from time import monotonic

import anyio

from noris_ai.core.config import Settings
from noris_ai.llm.continuation import ContinuationFilter, continuation_messages, utf16_length
from noris_ai.llm.errors import LLMError
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
        self._active: set[str] = set()
        self._recent: deque[float] = deque()
        self._budget_day = datetime.now(UTC).date()
        self._reserved_tokens = 0
        self._title_attempts: set[str] = set()
        self._counter = TokenCounter(config)
        self._answer_targets: dict[str, tuple[str, str]] = {}
        self._continuation_ids: set[str] = set()

    def reserve(self, request: ChatRequest) -> None:
        for message in request.messages:
            limit = (
                self.config.llm_max_message_chars
                if message.role == "user"
                else self.config.llm_max_response_chars
            )
            if utf16_length(message.content) > limit:
                raise LLMError("REQUEST_TOO_LARGE", 413)
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
        self._reserve(request.generationId, request.modelId, continuation_messages(request))
        self._answer_targets[request.generationId] = target
        if request.operation == "continue":
            self._continuation_ids.add(request.generationId)

    def _reserve(
        self,
        generation_id: str,
        model_id: str,
        messages: Sequence[ProviderMessage],
        output_limit: int | None = None,
    ) -> LLMModel:
        if self.provider is None:
            raise LLMError("LLM_DISABLED", 503)
        model = next((m for m in self.config.llm_models if m.id == model_id), None)
        if model is None or not model.available or not model.streaming:
            raise LLMError("MODEL_UNAVAILABLE", 400)
        # UTF-8 byte count is a deliberately conservative bound, not a tokenizer claim.
        if output_limit is not None:
            model = model.model_copy(
                update={"max_output_tokens": min(output_limit, model.max_output_tokens)}
            )
        estimate = self._counter.estimate(messages, model_id)
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
        self._active.add(generation_id)
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
            generation_id, request.modelId, messages, self.config.llm_title_max_output_tokens
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
        except LLMError:
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

    async def stream(self, request: ChatRequest) -> AsyncGenerator[bytes]:
        seq = 1
        yield self._encode(StartedEvent(seq=seq))
        provider = self.provider
        if provider is None:
            yield self._encode(
                FailedEvent(seq=2, code="LLM_DISABLED", message=LLMError("LLM_DISABLED").message)
            )
            return
        model = next(m for m in self.config.llm_models if m.id == request.modelId)
        iterator = provider.stream(continuation_messages(request), model)
        previous = request.messages[-1].content if request.operation == "continue" else ""
        filter_ = ContinuationFilter(previous)
        text_length = utf16_length(previous)
        has_text = False
        received = 0
        pending: asyncio.Future[str] | None = None

        def output(delta: str) -> list[bytes]:
            nonlocal seq, text_length, has_text, received
            events: list[bytes] = []
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
                if received + len(encoded) > self.config.llm_max_stream_bytes - 1024:
                    break
                received += len(encoded)
                text_length += utf16_length(fragment)
                has_text = has_text or bool(fragment.strip())
                seq += 1
                events.append(encoded)
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
            async with asyncio.timeout(self.config.llm_total_timeout_seconds):
                while True:
                    pending = asyncio.ensure_future(anext(iterator))
                    while not pending.done():
                        done, _ = await asyncio.wait(
                            {pending}, timeout=self.config.llm_heartbeat_seconds
                        )
                        if not done:
                            heartbeat = b": heartbeat\n\n"
                            received += len(heartbeat)
                            if received > self.config.llm_max_stream_bytes - 1024:
                                raise LLMError("STREAM_SIZE_LIMIT")
                            yield heartbeat
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
            yield self._encode(CompletedEvent(seq=seq + 1))
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
                    yield self._encode(IncompleteEvent(seq=seq + 1))
                    return
            yield self._encode(FailedEvent(seq=seq + 1, code=error.code, message=error.message))
        except Exception:
            error = LLMError("INTERNAL_ERROR", 500)
            yield self._encode(FailedEvent(seq=seq + 1, code=error.code, message=error.message))
        finally:
            # ASGI disconnect uses level cancellation: shield the upstream cleanup
            # so a second cancellation cannot interrupt socket closure.
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

    @staticmethod
    def _encode(
        event: StartedEvent | DeltaEvent | CompletedEvent | IncompleteEvent | FailedEvent,
    ) -> bytes:
        return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n".encode()
