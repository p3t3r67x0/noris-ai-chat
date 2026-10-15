import json
from dataclasses import replace
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from noris_ai.chat.repository import ModelDatabase
from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import ChatRequest
from noris_ai.main import create_app
from noris_ai.tools.budget import BudgetAmount
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.policy import ToolPermission, ToolPolicy
from noris_ai.tools.registry import create_tool_registry
from noris_ai.tools.schemas import SearchInput, SearchResult
from tests.fixtures.tool_budget import MemoryTextBudget
from tests.unit.test_llm_api import AUTH, PAYLOAD, FixtureProvider


async def handler(context: GenerationToolContext, value: SearchInput) -> SearchResult:
    raise RuntimeError("Never called by a public API")


@pytest.mark.parametrize(
    "decision,code", [("allow", None), ("approval_required", None), ("deny", "TOOL_FORBIDDEN")]
)
def test_policy_defaults_and_explicit_decisions(decision: str, code: str | None) -> None:
    definition = replace(
        create_tool_registry().get("web.search.v1"),
        handler=handler,
        provider_key="fixture",
        cost_policy="bounded",
    )
    with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
        ToolPolicy().require(definition)
    from typing import Literal, cast

    permission = ToolPermission(
        "fixture",
        "v1",
        cast(Literal["allow", "approval_required", "deny"], decision),
        BudgetAmount(calls=1),
        BudgetAmount(calls=1),
        BudgetAmount(calls=1),
    )
    policy = ToolPolicy({definition.name: permission})
    if code:
        with pytest.raises(ToolError, match=code):
            policy.require(definition)
    else:
        assert policy.require(definition) == permission
    for change in ({"handler": None}, {"provider_key": None}, {"cost_policy": "disabled"}):
        with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
            policy.require(replace(definition, **change))


@pytest.mark.parametrize(
    "value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("0.000000001")]
)
def test_unknown_negative_or_imprecise_costs_rejected(value: Decimal) -> None:
    with pytest.raises(ValueError):
        BudgetAmount(cost=value)


def operator_permission() -> dict[str, object]:
    return {
        "decision": "allow",
        "config_version": "review-v1",
        "per_call": {"calls": 1, "bytes": 65_536},
        "daily_limit": {"calls": 100, "bytes": 26_214_400},
        "generation_limit": {"calls": 6, "bytes": 2_097_152},
    }


def test_explicit_operator_config_uses_existing_policy_without_implicit_grants():
    assert not ToolPolicy.from_operator_json(None).permissions
    assert not ToolPolicy.from_operator_json("").permissions
    payload = {"version": 1, "web_search": operator_permission()}
    policy = ToolPolicy.from_operator_json(json.dumps(payload))
    assert set(policy.permissions) == {"web.search.v1"}
    definition = replace(
        create_tool_registry().get("web.search.v1"),
        handler=handler,
        provider_key="searxng",
        cost_policy="bounded",
    )
    assert policy.require(definition).per_call == BudgetAmount(calls=1, bytes=65_536)
    # A permission does not create a provider or activate research.
    with pytest.raises(ToolError):
        policy.require(create_tool_registry().get("web.search.v1"))


@pytest.mark.parametrize(
    "update",
    [
        {"version": 2},
        {"version": True},
        {"version": 1.0},
        {"version": "1"},
        {"version": None},
        {"execute": "web.search.v1"},
        {"owner_id": "forged"},
        {"web_search": {**operator_permission(), "url": "https://example.org"}},
        {"web_search": {**operator_permission(), "decision": "automatic"}},
        {"web_search": {**operator_permission(), "per_call": {"calls": True, "bytes": 1}}},
        {"web_search": {**operator_permission(), "daily_limit": {"calls": 0, "bytes": 0}}},
    ],
)
def test_operator_config_rejects_unknown_fields_permissions_and_unbounded_budgets(
    update: dict[str, object],
):
    with pytest.raises(ValueError):
        ToolPolicy.from_operator_json(json.dumps({"version": 1, **update}))


@pytest.mark.parametrize("payload", ['{"secret":"synthetic-private-config"}', "x" * 16_385])
async def test_invalid_operator_config_fails_closed_without_breaking_normal_chat(
    payload: str,
    llm_config: Settings,
    caplog: pytest.LogCaptureFixture,
):
    config = llm_config.model_copy(update={"tool_permissions_json": payload})
    app = create_app(config, provider=FixtureProvider())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=AUTH) as client,
    ):
        assert not cast(ToolPolicy, app.state.tool_runtime.policy).permissions
        assert (await client.post("/api/v1/llm/chat", json=PAYLOAD)).status_code == 200
    assert "synthetic-private-config" not in caplog.text


@pytest.mark.parametrize(
    "enabled,decision,expected",
    [(True, "allow", True), (False, "allow", False), (True, "approval_required", False)],
)
async def test_operator_configuration_reaches_existing_authorized_research_capability(
    llm_config: Settings,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    decision: str,
    expected: bool,
):
    monkeypatch.setenv("NORIS_SEARXNG_BASE_URL", "https://search.example.org")
    monkeypatch.setenv("NORIS_SEARXNG_ALLOWED_HOSTS", '["search.example.org"]')
    monkeypatch.setenv("NORIS_SEARXNG_ALLOWED_ADDRESSES", "[]")
    monkeypatch.setenv("NORIS_SEARXNG_CONFIG_VERSION", "review-v1")
    monkeypatch.setenv("NORIS_SOURCE_FETCH_CONFIG_VERSION", "p7a-v1")
    monkeypatch.setenv("NORIS_SOURCE_FETCH_ALLOW_HTTP", "false")
    payload = {
        "version": 1,
        "web_search": {**operator_permission(), "decision": decision},
        "web_fetch": {**operator_permission(), "config_version": "p7a-v1"},
    }
    config = llm_config.model_copy(
        update={
            "research_enabled": enabled,
            "searxng_enabled": True,
            "source_fetch_enabled": True,
            "tool_permissions_json": json.dumps(payload),
        }
    )
    app = create_app(config, provider=FixtureProvider())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/api/v1/chat/research/capability")).status_code == 401
        response = await client.get("/api/v1/chat/research/capability", auth=AUTH)
        assert response.status_code == 200
        assert response.json()["available"] is expected


async def test_capabilities_authenticated_and_no_execution_api(llm_config: Settings) -> None:
    app = create_app(llm_config)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/api/v1/chat/tools/capabilities")).status_code == 401
        response = await client.get("/api/v1/chat/tools/capabilities", auth=AUTH)
        assert response.status_code == 200
        assert all(f["status"] == "unavailable" for f in response.json()["features"])
        assert all(f["reasonCode"] == "TOOL_UNAVAILABLE" for f in response.json()["features"])
        assert "provider-key" not in response.text
        assert (
            await client.post(
                "/api/v1/chat/tools/execute", auth=AUTH, json={"tool": "web.search.v1"}
            )
        ).status_code == 404
        denied = await client.post(
            "/api/v1/chat/tool-approvals/00000000-0000-4000-8000-000000000001/decision",
            auth=AUTH,
            headers={"Origin": "https://evil.example"},
            json={
                "requestId": "00000000-0000-4000-8000-000000000002",
                "inputDigest": "a" * 64,
                "decision": "approve",
            },
        )
        assert denied.status_code == 403


async def test_budget_cleanup_outage_preserves_answer_and_releases_admission(
    llm_config: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailedSettlement(MemoryTextBudget):
        async def finish_text(self, owner: UUID, phase: str, *, unknown: bool = False) -> None:
            raise OperationalError("private SQL", {}, RuntimeError("secret database details"))

    budget = FailedSettlement(cast(ModelDatabase, MagicMock()))
    gateway = LLMGateway(
        llm_config.model_copy(update={"llm_max_concurrent": 1}), FixtureProvider(), budget
    )
    request = ChatRequest.model_validate(PAYLOAD)
    await gateway.reserve(request)
    events = [event async for event in gateway.events(request)]
    assert events[-1] is not None and events[-1].type == "response.completed"
    assert budget.phases[(llm_config.chat_owner_id, request.generationId)] == "dispatched"
    assert "Could not finalize text budget reservation" in caplog.text
    assert "secret" not in caplog.text and "private SQL" not in caplog.text
    next_request = request.model_copy(update={"generationId": "after-cleanup"})
    await gateway.reserve(next_request)  # A leaked admission would reject this with RATE_LIMIT.
    await gateway.abandon(next_request.generationId)
