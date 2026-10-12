"""Exact model contracts and the final provider boundary, without live calls."""

import json

import httpx
import pytest

from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.reasoning import apply_preference, preference_mapping
from noris_ai.llm.registry import REGISTRY
from noris_ai.llm.schemas import LLMMessage, ReasoningPreference


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("vllm/release/gpt-oss-120b", {"instant": "low", "medium": "medium", "high": "high"}),
        ("vllm/release/glm-5-2", {"high": "high", "very_high": "max"}),
        ("vllm/qsu/glm-5-3-flash", {}),
        ("vllm/qsu/deepseek-v41-flash", {}),
        ("vllm/qsu/qwen3.8-27b", {}),
        ("vllm/release/qwen3.6-27b", {}),
        ("vllm/release/gemma-4-31b-it", {}),
    ],
)
def test_all_current_models_require_an_evidenced_contract(
    model_id: str, expected: dict[str, str]
) -> None:
    assert preference_mapping(REGISTRY[model_id]) == expected


@pytest.mark.parametrize(
    "updates",
    [{"available": False}, {"streaming": False}, {"evidence": {"reasoning_parameter": "UNKNOWN"}}],
)
def test_revoked_and_unconfirmed_contracts_do_not_authorize_preferences(
    updates: dict[str, object],
) -> None:
    assert preference_mapping(REGISTRY["vllm/release/glm-5-2"].model_copy(update=updates)) == {}


@pytest.mark.parametrize(
    ("model_id", "preference", "parameter", "effort"),
    [
        ("vllm/release/gpt-oss-120b", "instant", "reasoning_effort", "low"),
        ("vllm/release/gpt-oss-120b", "medium", "reasoning_effort", "medium"),
        ("vllm/release/gpt-oss-120b", "high", "reasoning_effort", "high"),
        ("vllm/release/glm-5-2", "high", "chat_template_kwargs", "high"),
        ("vllm/release/glm-5-2", "very_high", "chat_template_kwargs", "max"),
    ],
)
async def test_ui_preferences_reach_only_their_documented_provider_parameter(
    llm_config: Settings,
    model_id: str,
    preference: ReasoningPreference,
    parameter: str,
    effort: str,
) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"Test"},'
                b'"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
            ),
        )

    original = REGISTRY[model_id]
    model = apply_preference(original, preference)
    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        assert [
            text async for text in provider.stream([LLMMessage(role="user", content="Test")], model)
        ] == ["Test"]
    finally:
        await provider.aclose()
    body = bodies[0]
    assert body[parameter] == (
        effort if parameter == "reasoning_effort" else {"reasoning_effort": effort}
    )
    other_parameter = (
        "reasoning_effort" if parameter == "chat_template_kwargs" else "chat_template_kwargs"
    )
    assert other_parameter not in body
    assert body[model.token_limit_parameter or "max_tokens"] == original.max_output_tokens
    assert model.context_window == original.context_window
    assert model.reasoning_reserve_tokens == original.reasoning_reserve_tokens


@pytest.mark.parametrize(
    ("model_id", "effort", "updates"),
    [
        (
            "vllm/release/gpt-oss-120b",
            "max",
            {"reasoning_efforts": ["low", "medium", "high", "max"]},
        ),
        ("vllm/release/glm-5-2", "low", {"reasoning_efforts": ["low", "high", "max"]}),
        ("vllm/release/glm-5-2", "max", {"reasoning_parameter": "reasoning_effort"}),
        ("vllm/release/glm-5-2", "max", {"evidence": {}}),
        ("vllm/release/glm-5-2", "max", {"available": False}),
        (
            "vllm/release/gemma-4-31b-it",
            "high",
            {
                "reasoning_parameter": "reasoning_effort",
                "reasoning_efforts": ["high"],
                "evidence": {"reasoning_parameter": "VERIFIED"},
            },
        ),
    ],
)
async def test_provider_never_forwards_incompatible_or_invented_efforts(
    llm_config: Settings, model_id: str, effort: str, updates: dict[str, object]
) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"index":0,"delta":{"content":"Test"},'
                b'"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
            ),
        )

    model = REGISTRY[model_id].model_copy(update={**updates, "reasoning_effort": effort})
    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    try:
        assert [
            text async for text in provider.stream([LLMMessage(role="user", content="Test")], model)
        ] == ["Test"]
    finally:
        await provider.aclose()
    assert "reasoning_effort" not in bodies[0]
    assert "chat_template_kwargs" not in bodies[0]


@pytest.mark.parametrize("preference", ["instant", "medium", "pro"])
def test_glm_rejects_preferences_from_other_profiles(preference: ReasoningPreference) -> None:
    with pytest.raises(LLMError, match="Denkstufe"):
        apply_preference(REGISTRY["vllm/release/glm-5-2"], preference)


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("vllm/release/gpt-oss-120b", {"instant": "low", "medium": "medium", "high": "high"}),
        ("vllm/release/glm-5-2", {"high": "high", "very_high": "max"}),
        ("vllm/qsu/glm-5-3-flash", {}),
        ("vllm/qsu/deepseek-v41-flash", {}),
        ("vllm/qsu/qwen3.8-27b", {}),
        ("vllm/release/qwen3.6-27b", {}),
        ("vllm/release/gemma-4-31b-it", {}),
    ],
)
def test_boolean_reasoning_in_provider_24_does_not_establish_effort_levels(
    llm_config: Settings, model_id: str, expected: dict[str, str]
) -> None:
    from noris_ai.llm.provider_models import ProviderModel
    from noris_ai.llm.registry import resolve_model

    # Relevant parameter semantics from the supplied 2026-10-12 GET /models.
    facts = ProviderModel.model_validate(
        {
            "id": model_id,
            "schema_version": "2.4",
            "is_ready": True,
            "input_modalities": [
                {
                    "type": "text",
                    "supported_inputs": {"max_context_length": {"value": 131072, "unit": "token"}},
                }
            ],
            "output_modalities": [
                {
                    "type": "text",
                    "streaming": True,
                    "supported_parameters": {
                        "max_tokens": {"max": 8192, "min": 1, "type": "integer", "unit": "token"},
                        **({"reasoning": {"type": "boolean"}} if "gemma" not in model_id else {}),
                    },
                }
            ],
        }
    )
    model = resolve_model(facts, llm_config)
    assert model.available
    assert preference_mapping(model) == expected
    if expected:
        assert model.provenance["reasoning_parameter"] == "LOCAL_POLICY"
        assert model.evidence["reasoning_parameter"] in ("DOCUMENTED", "VERIFIED")
