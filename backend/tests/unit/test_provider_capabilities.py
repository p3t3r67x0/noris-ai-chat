import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from noris_ai.core.config import Settings
from noris_ai.llm.catalog import ModelCatalogService
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.pricing import estimate_cost, model_cost
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.registry import REGISTRY, chat_compatible, resolve_model
from noris_ai.llm.schemas import LLMModel

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/noris-models-2.4.json"
DEEPSEEK = "vllm/qsu/deepseek-v41-flash"
QWEN = "vllm/qsu/qwen3.8-27b"


def payload() -> dict[str, Any]:
    # Account flags in this fixture are synthetic, prices are historical catalog quotes.
    return json.loads(FIXTURE.read_text())


def raw(model_id: str = DEEPSEEK) -> dict[str, Any]:
    return next(item for item in payload()["data"] if item["id"] == model_id)


def resolve(data: dict[str, Any], config: Settings) -> LLMModel:
    return resolve_model(ProviderModel.model_validate(data), config)


async def test_full_24_catalog_and_account_entitlements(llm_config: Settings) -> None:
    provider = OpenAICompatibleProvider(
        llm_config, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload()))
    )
    try:
        discovered = await provider.discover_models()
        assert len(discovered) == 10
        assert discovered[0].input_modalities
        result = await ModelCatalogService(llm_config, provider).get()
        assert len(result.models) == 7
        assert {DEEPSEEK, QWEN} <= {model.id for model in result.models}
        assert not any(model.virtual for model in result.models)
        assert all(model.is_ready is True and model.chat_approved for model in result.models)
        names = {model.name for model in result.models}
        assert {"DeepSeek V4.1 Flash", "Qwen3.8 27B", "Qwen3.6 27B"} <= names
        assert all(not model.vision for model in result.models)
        assert all(model.max_output_tokens <= 8192 for model in result.models)
        qwen = next(model for model in result.models if model.id.endswith("qwen3.6-27b"))
        assert qwen.provider_max_output_tokens == 8192
        assert qwen.effective_max_output_tokens == qwen.max_output_tokens == 4096
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    "model_id,context",
    [
        (DEEPSEEK, 1048576),
        ("vllm/qsu/glm-5-3-flash", 1048576),
        ("vllm/release/glm-5-2", 1048576),
        ("vllm/release/gpt-oss-120b", 131072),
    ],
)
def test_reported_context_is_not_local_policy(
    llm_config: Settings, model_id: str, context: int
) -> None:
    model = resolve(raw(model_id), llm_config)
    assert model.provider_context_window == context
    assert model.context_window == model.effective_context_window
    assert model.context_window <= 16384
    assert model.provider_max_output_tokens == context
    assert model.verified_max_output_tokens is None
    assert model.provenance["provider_context_window"] == "PROVIDER"
    assert model.provenance["effective_context_window"] == "LOCAL_POLICY"


@pytest.mark.parametrize(
    "model_id,category",
    [
        ("vllm/release/harrier-oss-v1-0.6b", "EMBEDDING"),
        ("vllm/release/bge-reranker-v2-m3", "RERANKING"),
        ("vllm/release/jina-reranker-v2-base-multilingual", "RERANKING"),
    ],
)
def test_non_chat_modalities_cannot_be_overridden(
    llm_config: Settings,
    model_id: str,
    category: str,
) -> None:
    override = llm_config.llm_models[0].model_copy(update={"id": model_id})
    model = resolve(raw(model_id), llm_config.model_copy(update={"llm_models": (override,)}))
    assert model.category == category
    assert not chat_compatible(model)


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_ready", False),
        ("is_ready", None),
        ("schema_version", "3.0"),
        ("input_modalities", None),
        ("output_modalities", None),
    ],
)
def test_missing_or_incompatible_contract_is_closed(
    llm_config: Settings,
    field: str,
    value: object,
) -> None:
    data = raw()
    data[field] = value
    assert not chat_compatible(resolve(data, llm_config))


@pytest.mark.parametrize("version", ["2.4", "2.5", "2.3", None])
def test_compatible_schema_additions_are_tolerated(
    llm_config: Settings, version: str | None
) -> None:
    data = raw()
    data.update(schema_version=version, unrelated_private_field="never-export")
    data["input_modalities"][0]["extra"] = True
    model = resolve(data, llm_config)
    assert chat_compatible(model)
    assert "never-export" not in model.model_dump_json()


def test_unknown_model_requires_explicit_contract_approval(llm_config: Settings) -> None:
    data = raw()
    data["id"] = "new-model-next-month"
    assert not chat_compatible(resolve(data, llm_config))
    approved = llm_config.llm_models[0].model_copy(update={"id": data["id"]})
    model = resolve(data, llm_config.model_copy(update={"llm_models": (approved,)}))
    assert chat_compatible(model) and model.name == "Fixture Alpha"
    data["output_modalities"][0]["streaming"] = False
    assert not chat_compatible(
        resolve(data, llm_config.model_copy(update={"llm_models": (approved,)}))
    )


def test_units_prices_limits_and_override_provenance(llm_config: Settings) -> None:
    data = raw()
    data["input_modalities"][0]["supported_inputs"]["max_context_length"]["unit"] = "byte"
    data["output_modalities"][0]["supported_parameters"]["max_tokens"]["unit"] = "byte"
    data["output_modalities"][0]["max_length"]["unit"] = "byte"
    data["input_modalities"][0]["pricing"][0]["unit"] = "request"
    model = resolve(data, llm_config)
    assert model.provider_context_window is None and model.provider_max_output_tokens is None
    assert model.context_window <= 8192 and model.max_output_tokens <= 1024
    assert model.cost.input_usd_per_million is None
    assert model.estimated_max_cost_usd is None
    assert model.provenance["provider_context_window"] == "UNKNOWN"


def test_output_uses_smallest_applicable_bound(llm_config: Settings) -> None:
    data = raw()
    data["output_modalities"][0]["max_length"]["value"] = 3000
    model = resolve(data, llm_config)
    assert model.provider_max_output_tokens == model.max_output_tokens == 3000
    # Validate a policy with a tested bound: no effective increase beyond that bound.
    policy = llm_config.llm_models[0].model_copy(
        update={
            "id": DEEPSEEK,
            "max_output_tokens": 2048,
            "verified_max_output_tokens": 2048,
            "provider_limit_evidence": "Synthetic test evidence",
        }
    )
    config = llm_config.model_copy(update={"llm_models": (policy,), "llm_max_output_tokens": 4096})
    model = resolve(data, config)
    assert model.provider_max_output_tokens == 3000
    assert model.verified_max_output_tokens == model.max_output_tokens == 2048


def test_prices_are_exact_dated_usd_and_not_points(llm_config: Settings) -> None:
    model = resolve(raw(), llm_config)
    assert model.cost.input_usd_per_million == Decimal("10")
    assert model.cost.cached_input_usd_per_million == Decimal("2")
    assert model.cost.output_usd_per_million == Decimal("30")
    assert model.cost.currency == "USD" and model.cost.as_of
    assert model.cost.input_points_per_million is None
    assert model.cost.model_dump(mode="json")["input_usd_per_million"] == "10.0000000000"
    assert estimate_cost(model.cost, 1000, 2000) == Decimal("0.07")
    unknown = model.cost.model_copy(update={"input_usd_per_million": None})
    assert estimate_cost(unknown, 1, 1) is None


def test_free_discount_missing_and_ambiguous_quotes(llm_config: Settings) -> None:
    data = raw()
    data.update(is_free=True, discount_to_user=15)
    cost = model_cost(ProviderModel.model_validate(data), "2026-10-10")
    assert estimate_cost(cost, 1000000, 1000000) == 0
    assert cost.discount_to_user == 15 and not cost.discount_applied
    data["input_modalities"][0]["pricing"] = []
    data["output_modalities"][0]["pricing"] = []
    cost = resolve(data, llm_config).cost
    assert cost.currency is None and cost.evidence == "UNKNOWN"
    data = raw()
    data["input_modalities"][0]["pricing"].append(
        {"type": "prompt", "unit": "token", "cost_usd": "0.01"}
    )
    assert resolve(data, llm_config).cost.input_usd_per_million is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_ready", "true"),
        ("id", "https://bad/?x"),
        ("created", True),
        ("input_modalities", {}),
        ("output_modalities", [{"type": "text", "streaming": "true"}]),
    ],
)
def test_invalid_used_fields_are_rejected(field: str, value: object) -> None:
    data = raw()
    data[field] = value
    with pytest.raises(ValidationError):
        ProviderModel.model_validate(data)


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-0.1", True, "not-usd"])
def test_invalid_prices_never_become_zero(price: object) -> None:
    data = raw()
    data["input_modalities"][0]["pricing"][0]["cost_usd"] = price
    with pytest.raises((ValidationError, ValueError)):
        ProviderModel.model_validate(data)


async def test_malformed_entry_and_duplicate_are_isolated(llm_config: Settings) -> None:
    data = payload()
    data["data"] += [raw(), {"id": "broken", "is_ready": "true"}]
    provider = OpenAICompatibleProvider(
        llm_config, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    )
    try:
        models = await provider.discover_models()
        assert len(models) == 9 and all(item.id not in (DEEPSEEK, "broken") for item in models)
    finally:
        await provider.aclose()


def test_vision_and_reasoning_require_evidence(llm_config: Settings) -> None:
    data = raw()
    assert resolve(data, llm_config).reasoning is None
    data["input_modalities"].append({"type": "image"})
    assert resolve(data, llm_config).vision is True
    data["output_modalities"][0]["supported_parameters"]["reasoning_effort"] = {"type": "string"}
    assert resolve(data, llm_config).reasoning is True


@pytest.mark.parametrize(
    "model_id,effort",
    [
        (DEEPSEEK, None),
        (QWEN, None),
        ("vllm/release/gpt-oss-120b", "low"),
        ("vllm/release/glm-5-2", "max"),
    ],
)
async def test_native_catalog_stream_keeps_exact_id_limits_and_reasoning_contract(
    llm_config: Settings,
    model_id: str,
    effort: str | None,
) -> None:
    from noris_ai.llm.gateway import LLMGateway
    from noris_ai.llm.schemas import ChatRequest, LLMMessage

    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload())
        calls.append(json.loads(request.content))
        data = (
            'data: {"choices":[{"index":0,"delta":{"content":"Hallo"}}]}\n\n'
            'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=data)

    policy = REGISTRY[model_id].model_copy(update={"reasoning_effort": effort})
    config = llm_config.model_copy(update={"llm_models": (policy,)})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))
    gateway = LLMGateway(config, provider)
    request = ChatRequest(
        generationId="native-stream",
        conversationId="chat",
        inputMessageId="input",
        modelId=model_id,
        messages=[LLMMessage(role="user", content="Hallo")],
        attempt=1,
    )
    try:
        await gateway.reserve(request)
        assert gateway._estimated_costs[request.generationId] is not None  # pyright: ignore[reportPrivateUsage]
        events = [chunk async for chunk in gateway.stream(request)]
        assert b"response.completed" in b"".join(events)
        assert len(calls) == 1 and calls[0]["model"] == model_id
        assert calls[0]["max_tokens"] <= 8192
        if model_id.endswith("gpt-oss-120b"):
            assert calls[0]["reasoning_effort"] == "low"
        elif model_id.endswith("glm-5-2"):
            assert calls[0]["chat_template_kwargs"] == {"reasoning_effort": "max"}
        else:
            assert "reasoning_effort" not in calls[0] and "chat_template_kwargs" not in calls[0]
    finally:
        await provider.aclose()


def test_compliance_and_datacenters_are_typed_and_extra_fields_are_private(
    llm_config: Settings,
) -> None:
    data = raw()
    data.update(
        hugging_face_id="fixture/public-model",
        datacenters=[{"country_code": "DE", "private_account": "never-export"}],
        compliance={"zdr": True, "hipaa": False, "unknown": "never-export"},
    )
    model = resolve(data, llm_config)
    assert model.hugging_face_id == "fixture/public-model"
    assert model.provider_datacenters == ["DE"]
    assert model.provider_compliance == {"zdr": True, "hipaa": False}
    assert "never-export" not in model.model_dump_json()


@pytest.mark.parametrize(
    "field,value",
    [
        ("compliance", {"zdr": "true"}),
        ("datacenters", [{"country_code": 42}]),
    ],
)
def test_invalid_additional_used_facts_are_rejected(field: str, value: object) -> None:
    data = raw()
    data[field] = value
    with pytest.raises(ValidationError):
        ProviderModel.model_validate(data)


def test_operator_denial_cannot_be_reversed_by_provider_readiness(llm_config: Settings) -> None:
    policy = LLMModel(id=DEEPSEEK, name="Blocked by operator", available=False)
    config = llm_config.model_copy(update={"llm_models": (policy,)})
    assert not chat_compatible(resolve(raw(), config))


async def test_invalid_duplicate_cannot_leave_old_entitlement(llm_config: Settings) -> None:
    valid = raw()
    invalid = raw()
    invalid["is_ready"] = "true"
    provider = OpenAICompatibleProvider(
        llm_config,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": [valid, invalid]})
        ),
    )
    try:
        assert await provider.discover_models() == []
    finally:
        await provider.aclose()


def test_live_test_reference_is_required() -> None:
    with pytest.raises(ValidationError, match="verification reference"):
        LLMModel(id="fixture-reference", name="Reference", verified_max_output_tokens=1024)
