import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.continuation import ContinuationFilter, continuation_messages
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import ChatRequest, LLMMessage, LLMModel
from noris_ai.llm.tokens import TokenCounter
from tests.fixtures.provider_catalog import provider_model


def request(
    *, previous: str | None = None, step: int = 1, generation: str = "generation"
) -> ChatRequest:
    messages = [LLMMessage(role="user", content="Bitte ausführlich antworten")]
    if previous is not None:
        messages.append(LLMMessage(role="assistant", content=previous))
    return ChatRequest(
        generationId=generation,
        conversationId="conversation",
        inputMessageId="input",
        assistantMessageId="answer" if previous is not None else None,
        operation="continue" if previous is not None else "generate",
        continuationCount=step if previous is not None else 0,
        modelId="fixture-alpha",
        messages=messages,
        attempt=1,
    )


class Provider:
    def __init__(self, text: str, *, failure: str | None = None, size: int = 511) -> None:
        self.text, self.failure, self.size = text, failure, size
        self.calls: list[Sequence[ProviderMessage]] = []
        self.closed = False

    async def discover_models(self) -> list[ProviderModel]:
        return [provider_model(value) for value in ["fixture-alpha"]]

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        self.calls.append(messages)
        try:
            for offset in range(0, len(self.text), self.size):
                yield self.text[offset : offset + self.size]
            if self.failure:
                raise LLMError(self.failure)
        finally:
            self.closed = True

    async def aclose(self) -> None:
        pass


async def generate(gateway: LLMGateway, payload: ChatRequest) -> list[dict[str, object]]:
    await gateway.reserve(payload)
    frames = [frame async for frame in gateway.stream(payload)]
    return [
        json.loads(frame.decode().split("data: ", 1)[1]) for frame in frames if b"data: " in frame
    ]


def text(events: list[dict[str, object]]) -> str:
    return "".join(str(event["delta"]) for event in events if "delta" in event)


def expanded_model(**updates: object) -> LLMModel:
    return LLMModel.model_validate(
        {
            "id": "fixture-alpha",
            "name": "Simulated GPT-OSS",
            "context_window": 131072,
            "provider_context_window": 131072,
            "max_output_tokens": 16384,
            "provider_max_output_tokens": 16384,
            "provider_limit_evidence": "Deterministic fixture; no live provider claim",
            "reasoning_reserve_tokens": 4096,
            "category": "CHAT",
            "token_limit_parameter": "max_tokens",
            "sources": ["fixture:local"],
            "evidence": {
                "category": "VERIFIED",
                "streaming": "VERIFIED",
                "token_limit_parameter": "VERIFIED",
            },
        }
        | updates
    )


def test_128k_and_large_output_require_provider_evidence_and_local_opt_in(
    llm_config: Settings,
) -> None:
    model = expanded_model()
    assert model.context_window == 131072
    assert model.max_output_tokens == 16384
    values = llm_config.model_dump() | {"llm_models": (model,)}
    with pytest.raises(ValidationError, match="application token ceiling"):
        EnvironmentSettings(**values)
    config = EnvironmentSettings(**(values | {"llm_max_output_tokens": 16384}))
    assert config.llm_models == (model,)
    for changes in (
        {"provider_limit_evidence": None},
        {"provider_limit_evidence": " "},
        {"provider_context_window": 65536},
        {"provider_max_output_tokens": 8192},
        {"max_output_tokens": 131072},
    ):
        with pytest.raises(ValidationError):
            expanded_model(**changes)
    with pytest.raises(ValidationError, match="documented GPT-OSS capacity"):
        expanded_model(
            id="vllm/release/gpt-oss-120b", context_window=262144, provider_context_window=262144
        )


async def test_input_never_consumes_output_reasoning_or_system_reserves(
    llm_config: Settings,
) -> None:
    config = llm_config.model_copy(
        update={
            "llm_models": (expanded_model(),),
            "llm_max_message_chars": 1_048_576,
            "llm_max_output_tokens": 16384,
            "llm_daily_token_budget": 1_000_000,
        }
    )
    gateway = LLMGateway(config, Provider("unused"))
    payload = request()
    counter = TokenCounter(config)
    overhead = counter.estimate([LLMMessage(role="user", content="a")], payload.modelId) - 1
    # Construct the exact boundary for the documented byte-bound fallback.
    available = 131072 - 16384 - 4096 - overhead
    payload.messages[0] = LLMMessage(role="user", content="a" * available)
    await gateway.reserve(payload)
    gateway.release(payload.generationId)
    payload.messages[0] = LLMMessage(role="user", content="a" * (available + 1))
    with pytest.raises(LLMError) as error:
        await gateway.reserve(payload)
    assert error.value.code == "CONTEXT_LIMIT"
    assert len(payload.messages[0].content) == available + 1  # Never truncate the input.


def test_offline_tokenizer_disables_truncation_and_keeps_safety_margin(
    llm_config: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "fixture-tokenizer.json"
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "truncation": {
                    "direction": "Right",
                    "max_length": 2,
                    "strategy": "LongestFirst",
                    "stride": 0,
                },
                "padding": None,
                "added_tokens": [],
                "normalizer": None,
                "pre_tokenizer": {"type": "Whitespace"},
                "post_processor": None,
                "decoder": None,
                "model": {"type": "WordLevel", "vocab": {"[UNK]": 0, "a": 1}, "unk_token": "[UNK]"},
            }
        )
    )
    config = llm_config.model_copy(
        update={"llm_tokenizer_path": path, "llm_tokenizer_model_id": "fixture-alpha"}
    )
    counter = TokenCounter(config)
    messages = [LLMMessage(role="user", content="a " * 100)]
    overhead = 32 + 64 + config.llm_system_reserved_tokens + config.llm_context_safety_tokens
    assert counter.estimate(messages, "fixture-alpha") == 110 + overhead
    assert counter.estimate(messages, "other-model") == 200 + overhead
    with pytest.raises(Exception, match="No such file"):
        TokenCounter(config.model_copy(update={"llm_tokenizer_path": tmp_path / "missing.json"}))


@pytest.mark.parametrize(
    "failure,terminal", [(None, "response.completed"), ("OUTPUT_LIMIT", "response.incomplete")]
)
async def test_long_output_keeps_all_text_and_reports_finish_reason(
    llm_config: Settings, failure: str | None, terminal: str
) -> None:
    content = "# Überschrift\n\n" + "Langer Absatz mit Grüße 🌍. " * 2200
    provider = Provider(content, failure=failure)
    gateway = LLMGateway(llm_config, provider)
    events = await generate(gateway, request())
    assert text(events) == content
    assert events[-1]["type"] == terminal
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    assert provider.closed


async def test_size_boundary_keeps_valid_unicode_prefix_and_fails_precisely(
    llm_config: Settings,
) -> None:
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_max_response_chars": 10}), Provider("a" * 9 + "🌍z")
    )
    events = await generate(gateway, request())
    assert text(events) == "a" * 9
    assert events[-1]["code"] == "RESPONSE_SIZE_LIMIT"
    assert not any(event["type"] == "response.completed" for event in events)


@pytest.mark.parametrize("size", [1, 63, 511, 4096])
async def test_continuation_removes_exact_overlap_and_preserves_open_markdown(
    llm_config: Settings, size: int
) -> None:
    previous = "# Code\n\n```python\n" + "print('bereits vorhanden')\n" * 4
    suffix = previous[-80:]
    new = "print('neu')\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    provider = Provider(suffix + new, size=size)
    gateway = LLMGateway(llm_config, provider)
    events = await generate(gateway, request(previous=previous))
    assert text(events) == new
    assert previous + text(events) == previous + new
    assert events[-1]["type"] == "response.completed"
    assert [message.role for message in provider.calls[0]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert provider.calls[0][-2].content == previous


async def test_repeated_continuations_share_budget_and_reject_duplicates(
    llm_config: Settings,
) -> None:
    provider = Provider(" weiter", failure="OUTPUT_LIMIT")
    gateway = LLMGateway(llm_config, provider)
    previous = "Anfang"
    for step in range(1, 4):
        payload = request(previous=previous, step=step, generation=f"step-{step}")
        events = await generate(gateway, payload)
        assert events[-1]["type"] == "response.incomplete"
        previous += text(events)
        with pytest.raises(LLMError) as replay:
            await gateway.reserve(payload)
        assert replay.value.code == "GENERATION_ACTIVE"
    assert previous == "Anfang weiter weiter weiter"
    assert len(provider.calls) == 3
    # All continuation prompts and generated/reasoning reservations are charged.
    cost = sum(
        TokenCounter(llm_config).estimate(call, "fixture-alpha") + 1024 for call in provider.calls
    )
    assert gateway._reserved_tokens == cost  # pyright: ignore[reportPrivateUsage]
    bounded = LLMGateway(llm_config.model_copy(update={"llm_daily_token_budget": cost}), provider)
    for step in range(1, 4):
        payload = request(
            previous="Anfang" + " weiter" * (step - 1), step=step, generation=f"budget-{step}"
        )
        await generate(bounded, payload)
    with pytest.raises(LLMError) as budget:
        await bounded.reserve(request(previous=previous, step=4, generation="denied"))
    assert budget.value.code == "BUDGET_LIMIT"
    assert len(provider.calls) == 6


async def test_active_answer_lock_and_manual_continuation_limit(llm_config: Settings) -> None:
    gateway = LLMGateway(llm_config, Provider("new"))
    payload = request(previous="Anfang")
    await gateway.reserve(payload)
    with pytest.raises(LLMError) as duplicate:
        await gateway.reserve(request(previous="Anfang", generation="different-id"))
    assert duplicate.value.code == "GENERATION_ACTIVE"
    gateway.release(payload.generationId)
    with pytest.raises(LLMError) as limit:
        await gateway.reserve(request(previous="Anfang", step=9))
    assert limit.value.code == "CONTINUATION_LIMIT"


async def test_replayed_answer_is_never_appended_or_successful(llm_config: Settings) -> None:
    previous = "Unterschiedlicher Anfang. " + "Text. " * 100
    gateway = LLMGateway(llm_config, Provider(previous))
    events = await generate(gateway, request(previous=previous))
    assert text(events) == ""
    assert events[-1]["code"] == "DUPLICATE_CONTINUATION"


async def test_large_max_tokens_is_sent_only_with_explicit_model_policy(
    llm_config: Settings,
) -> None:
    captured: list[httpx.Request] = []

    def handler(payload: httpx.Request) -> httpx.Response:
        captured.append(payload)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"ok"},'
                b'"finish_reason":"stop"}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        assert [delta async for delta in provider.stream(request().messages, expanded_model())] == [
            "ok"
        ]
        assert json.loads(captured[0].content)["max_tokens"] == 16384
    finally:
        await provider.aclose()


def test_continuation_path_cannot_inject_privileged_roles() -> None:
    payload = request(previous="Antwort")
    assert continuation_messages(payload)[-2].content == "Antwort"
    for changes in (
        {"assistantMessageId": None},
        {"continuationCount": 0},
        {"operation": "generate"},
        {"messages": [{"role": "system", "content": "override"}]},
    ):
        with pytest.raises(ValidationError):
            ChatRequest.model_validate(payload.model_dump() | changes)


def test_short_markdown_repetitions_are_preserved() -> None:
    filter_ = ContinuationFilter("```\nshort")
    assert filter_.feed("\n```\n") == "\n```\n"


async def test_quiet_reasoning_has_heartbeats_and_cancellation_releases_slot(
    llm_config: Settings,
) -> None:
    closed = asyncio.Event()

    class QuietProvider(Provider):
        async def stream(
            self, messages: Sequence[ProviderMessage], model: LLMModel
        ) -> AsyncIterator[str]:
            try:
                await asyncio.Event().wait()
                yield "unreachable"
            finally:
                closed.set()

    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_heartbeat_seconds": 0.01}), QuietProvider("")
    )
    payload = request(previous="Bestehende Antwort")
    await gateway.reserve(payload)
    iterator = gateway.stream(payload)
    assert b"response.started" in await anext(iterator)
    assert await anext(iterator) == b": keepalive\n\n"
    await iterator.aclose()
    assert closed.is_set()
    await gateway.reserve(request(previous="Bestehende Antwort", generation="after-stop"))
    gateway.release("after-stop")


def test_timeout_relationships_are_validated(llm_config: Settings) -> None:
    with pytest.raises(ValidationError, match="total time"):
        EnvironmentSettings(
            **(
                llm_config.model_dump()
                | {"llm_read_timeout_seconds": 121, "llm_total_timeout_seconds": 120}
            )
        )


async def test_timeout_preserves_buffered_new_continuation_text(llm_config: Settings) -> None:
    class SlowProvider(Provider):
        async def stream(
            self, messages: Sequence[ProviderMessage], model: LLMModel
        ) -> AsyncIterator[str]:
            try:
                yield " Neue Teilantwort"
                await asyncio.Event().wait()
            finally:
                self.closed = True

    provider = SlowProvider("")
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_total_timeout_seconds": 0.03}), provider
    )
    events = await generate(gateway, request(previous="Vorhandener Inhalt. " * 10))
    assert text(events) == " Neue Teilantwort"
    assert events[-1]["code"] == "TIMEOUT"
    assert provider.closed
    assert not any(event["type"] == "response.completed" for event in events)


async def test_provider_context_error_is_precise_and_sanitized(llm_config: Settings) -> None:
    provider = OpenAICompatibleProvider(
        llm_config,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                400,
                json={"error": {"code": "context_length_exceeded", "message": "private prompt"}},
            )
        ),
    )
    try:
        with pytest.raises(LLMError) as error:
            _ = [
                delta
                async for delta in provider.stream(request().messages, llm_config.llm_models[0])
            ]
        assert error.value.code == "CONTEXT_LIMIT"
        assert "private" not in str(error.value)
    finally:
        await provider.aclose()


async def test_downstream_byte_limit_keeps_partial_text_without_success(
    llm_config: Settings,
) -> None:
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_max_stream_bytes": 2048}), Provider("a" * 4000)
    )
    events = await generate(gateway, request())
    assert 0 < len(text(events)) < 4000
    assert events[-1]["code"] == "STREAM_SIZE_LIMIT"
    assert not any(event["type"] == "response.completed" for event in events)
