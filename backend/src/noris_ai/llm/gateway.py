import asyncio
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime
from time import monotonic

import anyio

from noris_ai.core.config import Settings
from noris_ai.llm.catalog import ModelCatalogService
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import LLMProvider, ProviderMessage
from noris_ai.llm.schemas import (
    ChatRequest,
    CompletedEvent,
    ConversationTitleRequest,
    ConversationTitleResponse,
    DeltaEvent,
    FailedEvent,
    LLMMessage,
    LLMModel,
    StartedEvent,
)
from noris_ai.llm.titles import TitleInstruction, title_source, validate_title


class LLMGateway:
    """Bounded, single-worker admission; never silently truncate or automatically retry."""

    def __init__(self, config: Settings, provider: LLMProvider | None) -> None:
        self.config = config
        self.provider = provider
        self.catalog = ModelCatalogService(config, provider)
        self._admitted: dict[str, LLMModel] = {}
        self._active: set[str] = set()
        self._recent: deque[float] = deque()
        self._budget_day = datetime.now(UTC).date()
        self._reserved_tokens = 0
        self._title_attempts: set[str] = set()

    async def reserve(self, request: ChatRequest) -> None:
        for message in request.messages:
            limit = (
                self.config.llm_max_message_chars
                if message.role == "user"
                else self.config.llm_max_response_chars
            )
            if len(message.content.encode("utf-16-le")) // 2 > limit:
                raise LLMError("REQUEST_TOO_LARGE", 413)
        model = await self.catalog.require(request.modelId)
        self._reserve(request.generationId, model, request.messages)

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
        estimate = (
            sum(len(m.content.encode("utf-8")) + 32 for m in messages)
            + 64
            + self.config.llm_context_safety_tokens
        )
        # Charge the full generated-token cap, including invisible reasoning, even
        # on Stop, length, failure or retry. Never refund based on visible text.
        reservation = estimate + model.max_output_tokens
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
        self._admitted.pop(generation_id, None)

    async def stream(self, request: ChatRequest) -> AsyncGenerator[bytes]:
        seq = 1
        started = self._encode(StartedEvent(seq=seq))
        yield started
        provider = self.provider
        if provider is None:
            yield self._encode(
                FailedEvent(seq=2, code="LLM_DISABLED", message=LLMError("LLM_DISABLED").message)
            )
            return
        model = self._admitted[request.generationId]
        iterator = provider.stream(request.messages, model)
        text_length = 0
        stream_bytes = len(started)
        has_text = False
        pending: asyncio.Future[str] | None = None
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
                            stream_bytes += len(heartbeat)
                            if stream_bytes + 512 > self.config.llm_max_stream_bytes:
                                raise LLMError("OUTPUT_LIMIT")
                            yield heartbeat
                    try:
                        delta = pending.result()
                    except StopAsyncIteration:
                        break
                    text_length += len(delta.encode("utf-16-le")) // 2
                    has_text = has_text or bool(delta.strip())
                    if text_length > self.config.llm_max_response_chars:
                        raise LLMError("OUTPUT_LIMIT")
                    encoded = self._encode(DeltaEvent(seq=seq + 1, delta=delta))
                    stream_bytes += len(encoded)
                    if stream_bytes + 512 > self.config.llm_max_stream_bytes:
                        raise LLMError("OUTPUT_LIMIT")
                    seq += 1
                    yield encoded
            if not has_text:
                raise LLMError("INVALID_RESPONSE")
            yield self._encode(CompletedEvent(seq=seq + 1))
        except TimeoutError:
            error = LLMError("TIMEOUT", 504)
            yield self._encode(FailedEvent(seq=seq + 1, code=error.code, message=error.message))
        except LLMError as error:
            if error.code in ("MODEL_UNAVAILABLE", "PROVIDER_AUTH_FAILED"):
                self.catalog.invalidate()
            yield self._encode(FailedEvent(seq=seq + 1, code=error.code, message=error.message))
        except Exception:
            error = LLMError("INTERNAL_ERROR", 500)
            yield self._encode(FailedEvent(seq=seq + 1, code=error.code, message=error.message))
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

    @staticmethod
    def _encode(event: StartedEvent | DeltaEvent | CompletedEvent | FailedEvent) -> bytes:
        return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n".encode()
