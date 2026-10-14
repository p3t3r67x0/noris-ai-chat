"""P7c catalog-derived coverage; no live discovery or external requests."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.registry import REGISTRY, chat_compatible
from noris_ai.llm.schemas import CatalogLLMModel, LLMModel, PersistedChatRequest
from noris_ai.research.grounding import GroundingContextBuilder
from noris_ai.research.planner import plan_research
from noris_ai.research.schemas import ResearchIntent
from tests.fixtures.provider_catalog import provider_model
from tests.unit.test_llm_api import FixtureProvider
from tests.unit.test_research import fetched, request


class AllCatalogProvider(FixtureProvider):
    async def discover_models(self):
        return [
            provider_model(model.id, vision=model.vision is True)
            for model in [*REGISTRY.values(), LLMModel(id="new-operator-model", name="Future")]
        ]


async def test_every_eligible_catalog_model_generates_grounded_text_without_tool_calling(
    llm_config: Settings,
):
    future = LLMModel(
        id="new-operator-model",
        name="Future",
        category="CHAT",
        context_window=4096,
        max_output_tokens=256,
        tool_calling=False,
        sources=["fixture:local"],
        token_limit_parameter="max_tokens",  # noqa: S106
        evidence={
            "category": "VERIFIED",
            "streaming": "VERIFIED",
            "token_limit_parameter": "VERIFIED",
        },
    )
    # Derive cases from the actual catalog. Names never select research behavior.
    config = llm_config.model_copy(update={"llm_models": (*llm_config.llm_models, future)})
    provider = AllCatalogProvider()
    gateway = LLMGateway(config, provider)
    catalog = await gateway.catalog.get()
    eligible = [model for model in catalog.models if model.research_eligible]
    assert eligible and any(model.id == future.id for model in eligible)
    assert all(model.research_eligible for model in catalog.models if chat_compatible(model))
    for model in eligible:
        base = request().model_copy(update={"generationId": str(uuid4()), "modelId": model.id})
        selected, capacity = await gateway.research_capacity(base)
        grounded = GroundingContextBuilder(gateway).build(base, selected, capacity, [fetched()])
        assert grounded.request.messages == base.messages
        await gateway.reserve(grounded.request)
        events = [event async for event in gateway.events(grounded.request)]
        assert events[-1] is not None and events[-1].type == "response.completed"
        assert provider.calls[-1][1].id == model.id
        assert provider.calls[-1][0][1].content.startswith("EXTERNAL_SOURCE_CONTENT")
    assert any(model.tool_calling is not True for model in eligible)
    assert any(model.reasoning is True for model in eligible)
    assert any(model.reasoning is not True for model in eligible)
    assert any(model.vision is True for model in eligible)
    assert any(model.vision is not True for model in eligible)
    assert any(model.context_window <= 4096 for model in eligible)


def test_explicit_web_selection_searches_non_current_question_but_keeps_privacy_filter():
    deadline = datetime.now(UTC) + timedelta(minutes=1)
    assert not plan_research("Was ist QGIS?", "de", deadline).searches
    assert plan_research("Was ist QGIS?", "de", deadline, explicit=True).searches
    with pytest.raises(ValueError):
        plan_research("Mein Kennwort ist private-test-value", "de", deadline, explicit=True)


@pytest.mark.parametrize(
    "extra",
    [
        {"owner_id": str(uuid4())},
        {"url": "https://example.org"},
        {"toolId": "web.search.v1"},
        {"version": 2},
        {"mode": "execute"},
    ],
)
def test_public_intent_cannot_supply_scope_tools_urls_or_new_versions(extra: dict[str, object]):
    with pytest.raises(ValidationError):
        ResearchIntent.model_validate_json(
            json.dumps({"version": 1, "mode": "web", "language": "de", **extra})
        )


def test_public_capability_is_derived_and_cannot_become_a_policy_input():
    model = LLMModel(id="new-model", name="New", chat_approved=True, tool_calling=False)
    assert model.research_eligible
    assert (
        CatalogLLMModel.model_validate(model.model_dump()).model_dump()["research_eligible"] is True
    )
    assert not model.model_copy(update={"is_ready": False}).research_eligible
    assert not model.model_copy(update={"input_modalities": ["image"]}).research_eligible
    assert not model.model_copy(update={"output_modalities": ["embeddings"]}).research_eligible
    with pytest.raises(ValidationError):
        LLMModel.model_validate(
            {**model.model_dump(exclude_computed_fields=True), "research_eligible": True}
        )
    assert PersistedChatRequest.model_fields.get("research") is None
