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
