import asyncio
import json
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest
from pydantic import ValidationError

from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.schemas import ChatRequest, LLMModel


def long_model(**updates: object) -> LLMModel:
    return LLMModel.model_validate(
        {
            "id": "fixture-alpha",
            "name": "Local long-output fixture",
            "context_window": 131_072,
            "max_output_tokens": 32_768,
            "provider_max_output_tokens": 32_768,
            "provider_limit_evidence": "Local simulator only; no Noris capacity claim",
        }
        | updates
    )


def request(content: str = "Hallo", generation_id: str = "long-output") -> ChatRequest:
    return ChatRequest.model_validate(
        {
            "generationId": generation_id,
            "conversationId": "conversation",
            "inputMessageId": "input",
            "modelId": "fixture-alpha",
            "messages": [{"role": "user", "content": content}],
            "attempt": 1,
        }
    )


def frame(delta: dict[str, str], finish: str | None = None) -> bytes:
    return (
        "data: "
        + json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]})
        + "\n\n"
    ).encode()


@pytest.mark.parametrize("finish", ["stop", "length"])
@pytest.mark.parametrize("token_parameter", ["max_tokens", "max_completion_tokens"])
async def test_over_8192_output_tokens_preserve_stream_and_length_failure(
    llm_config: Settings, finish: str, token_parameter: str
) -> None:
    # Each simulator delta represents one generated token; its usage reports 9001.
    data = frame({"reasoning_content": "private reasoning"})
    data += frame({"content": " token"}) * 9000 + frame({}, finish)
    data += b'data: {"choices": [], "usage": {"completion_tokens": 9001}}\n\n'
    data += b"data: [DONE]\n\n"
    captured: list[httpx.Request] = []

    def handler(upstream: httpx.Request) -> httpx.Response:
        captured.append(upstream)
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=data)

    config = llm_config.model_copy(
        update={
            "llm_models": (long_model(),),
            "llm_max_output_tokens": 32_768,
            "llm_daily_token_budget": 33_381,
            "llm_token_limit_parameter": token_parameter,
        }
    )
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))
    gateway = LLMGateway(config, provider)
    payload = request()
    gateway.reserve(payload)
    try:
        events = [chunk async for chunk in gateway.stream(payload)]
    finally:
        await provider.aclose()
    values = [json.loads(chunk.decode().split("data: ", 1)[1]) for chunk in events]
    deltas = [value["delta"] for value in values if value["type"] == "response.output_text.delta"]
    assert len(deltas) == 9000 and "".join(deltas) == " token" * 9000
    assert values[-1]["type"] == ("response.completed" if finish == "stop" else "response.failed")
    if finish == "length":
        assert values[-1]["code"] == "OUTPUT_LIMIT"
    assert [value["seq"] for value in values] == list(range(1, len(values) + 1))
    assert len(captured) == 1
    assert json.loads(captured[0].content)[token_parameter] == 32_768
    assert b"private reasoning" not in b"".join(events)
    # Same ID proves the slot was released; retained full reservation blocks a retry.
    with pytest.raises(LLMError) as budget:
        gateway.reserve(payload)
    assert budget.value.code == "BUDGET_LIMIT"


@pytest.mark.parametrize(
    "updates",
    [
        {"provider_max_output_tokens": 8192},
        {"provider_limit_evidence": None},
        {"provider_limit_evidence": " "},
        {"max_output_tokens": 131_072, "provider_max_output_tokens": 131_072},
        {"max_output_tokens": 131_073},
    ],
)
def test_expanded_output_requires_capacity_evidence_and_context(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        long_model(**updates)


def test_application_ceiling_and_timeout_configuration() -> None:
    with pytest.raises(ValidationError):
        EnvironmentSettings(llm_models=(long_model(),))
    config = EnvironmentSettings(llm_models=(long_model(),), llm_max_output_tokens=32_768)
    assert config.llm_daily_token_budget == 100_000
    with pytest.raises(ValidationError):
        EnvironmentSettings(llm_total_timeout_seconds=10, llm_read_timeout_seconds=120)


class QuietProvider:
    def __init__(self) -> None:
        self.closed = False

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        try:
            await asyncio.Event().wait()
            yield "unreachable"
        finally:
            self.closed = True

    async def aclose(self) -> None:
        pass


async def test_heartbeat_does_not_cancel_upstream_and_stop_releases_slot(
    llm_config: Settings,
) -> None:
    provider = QuietProvider()
    config = llm_config.model_copy(update={"llm_heartbeat_seconds": 0.01})
    gateway = LLMGateway(config, provider)
    payload = request()
    gateway.reserve(payload)
    iterator = gateway.stream(payload)
    assert b"response.started" in await anext(iterator)
    assert await anext(iterator) == b": keepalive\n\n"
    assert not provider.closed
    await iterator.aclose()
    assert provider.closed
    gateway.reserve(payload)
    gateway.release(payload.generationId)


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_configured_input_limits_use_utf16_and_assistant_has_separate_limit(
    llm_config: Settings, role: str
) -> None:
    config = llm_config.model_copy(
        update={"llm_max_message_chars": 10, "llm_max_response_chars": 20}
    )
    gateway = LLMGateway(config, QuietProvider())
    messages = [{"role": "user", "content": "x"}]
    if role == "user":
        messages[0]["content"] = "🌍" * 6
    else:
        messages += [{"role": "assistant", "content": "🌍" * 11}, {"role": "user", "content": "x"}]
    payload = ChatRequest.model_validate(request().model_dump() | {"messages": messages})
    with pytest.raises(LLMError) as raised:
        gateway.reserve(payload)
    assert raised.value.code == "REQUEST_TOO_LARGE"
    gateway.reserve(request())
    gateway.release("long-output")


def test_full_output_reservation_rejects_context_and_retry_budget(llm_config: Settings) -> None:
    config = llm_config.model_copy(
        update={
            "llm_models": (long_model(),),
            "llm_daily_token_budget": 40_000,
            "llm_max_message_chars": 131_072,
        }
    )
    gateway = LLMGateway(config, QuietProvider())
    with pytest.raises(LLMError) as context:
        gateway.reserve(request("x" * 98_000))
    assert context.value.code == "CONTEXT_LIMIT"
    gateway.reserve(request())
    gateway.release("long-output")
    with pytest.raises(LLMError) as budget:
        gateway.reserve(request(generation_id="manual-retry"))
    assert budget.value.code == "BUDGET_LIMIT"


class TextProvider:
    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        yield "🌍"
        yield "🌍"

    async def aclose(self) -> None:
        pass


async def test_gateway_configured_utf16_response_limit_preserves_accepted_text(
    llm_config: Settings,
) -> None:
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_max_response_chars": 3}), TextProvider()
    )
    gateway.reserve(request())
    events = b"".join([chunk async for chunk in gateway.stream(request())])
    assert events.decode().count('"delta":"🌍"') == 1
    assert b"OUTPUT_LIMIT" in events and b"response.completed" not in events


async def test_gateway_stream_byte_limit_includes_terminal_overhead(llm_config: Settings) -> None:
    class LargeProvider(TextProvider):
        async def stream(
            self, messages: Sequence[ProviderMessage], model: LLMModel
        ) -> AsyncIterator[str]:
            yield "x" * 1024

    config = llm_config.model_copy(update={"llm_max_stream_bytes": 1024})
    gateway = LLMGateway(config, LargeProvider())
    gateway.reserve(request())
    events = b"".join([chunk async for chunk in gateway.stream(request())])
    assert len(events) <= 1024
    assert b"OUTPUT_LIMIT" in events and b'"delta"' not in events


def test_long_assistant_history_is_accepted_without_expanding_user_limit(
    llm_config: Settings,
) -> None:
    config = llm_config.model_copy(update={"llm_models": (long_model(),)})
    gateway = LLMGateway(config, QuietProvider())
    payload = ChatRequest.model_validate(
        request().model_dump()
        | {
            "messages": [
                {"role": "user", "content": "Hallo"},
                {"role": "assistant", "content": " token" * 9000},
                {"role": "user", "content": "Weiter"},
            ]
        }
    )
    gateway.reserve(payload)
    gateway.release(payload.generationId)


@pytest.mark.parametrize("oversized", [False, True])
async def test_reasoning_only_length_is_failure_and_reasoning_bytes_are_bounded(
    llm_config: Settings,
    oversized: bool,
) -> None:
    data = frame({"reasoning_content": "private" * (1000 if oversized else 1)})
    data += frame({}, "length") + b"data: [DONE]\n\n"
    provider = OpenAICompatibleProvider(
        llm_config.model_copy(update={"llm_max_upstream_bytes": 1024}),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, headers={"Content-Type": "text/event-stream"}, content=data
            )
        ),
    )
    try:
        with pytest.raises(LLMError) as error:
            _ = [
                delta
                async for delta in provider.stream(request().messages, llm_config.llm_models[0])
            ]
        assert error.value.code == "OUTPUT_LIMIT"
    finally:
        await provider.aclose()
