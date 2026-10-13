"""P1b executes only local fake handlers against disposable PostgreSQL."""

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from noris_ai.chat.models import ChatConversation, ChatGeneration
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.service import ChatService
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.schemas import ChatRequest, ConversationTitleRequest, LLMMessage
from noris_ai.main import create_app
from noris_ai.tools.budget import BudgetAmount, BudgetCoordinator, BudgetDay, BudgetReservation
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolApproval, ToolResult, ToolRun
from noris_ai.tools.policy import ToolPermission, ToolPolicy
from noris_ai.tools.registry import RetryPolicy, TimeoutPolicy, ToolRegistry, create_tool_registry
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import SearchInput, SearchResult
from tests.integration import test_tool_foundation as foundation
from tests.integration.test_tool_foundation import INPUT, ToolFixture
from tests.unit.test_conversation_titles import TitleProvider
from tests.unit.test_llm_api import AUTH

tool_schema = foundation.tool_schema
tools = foundation.tools

pytestmark = pytest.mark.integration


class Simulator:
    def __init__(self) -> None:
        self.calls: list[GenerationToolContext] = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.wait = False
        self.error: str | None = None
        self.closed = False

    async def handle(self, context: GenerationToolContext, value: SearchInput) -> SearchResult:
        context.check()
        self.calls.append(context)
        self.entered.set()
        try:
            if self.wait:
                await self.release.wait()
            if self.error == "private":
                raise RuntimeError("secret provider body")
            if self.error == "retry" and len(self.calls) == 1:
                raise ToolError("PROVIDER_RATE_LIMIT")
            return SearchResult(
                sources=[],
                provider="searxng",
                config_version="fixture-v1",
                fetched_at=datetime.now(UTC),
            )
        finally:
            self.closed = True


@dataclass
class RuntimeFixture:
    base: ToolFixture
    runtime: ToolRuntime
    simulator: Simulator

    def request(self, step: str = "search"):
        return self.base.request(step).model_copy(
            update={"provider_key": "fixture", "config_version": "fixture-v1"}
        )


def configured(
    base: ToolFixture,
    simulator: Simulator,
    *,
    approval: bool = False,
    retries: int = 0,
    idempotent: bool = True,
    timeout: float = 15,
    daily_calls: int = 10,
    generation_calls: int = 10,
) -> ToolRuntime:
    definition = replace(
        create_tool_registry().get("web.search.v1"),
        handler=simulator.handle,
        provider_key="fixture",
        cost_policy="bounded",
        retry_policy=RetryPolicy(retries, idempotent),
        timeout_policy=TimeoutPolicy(timeout),
    )
    registry = ToolRegistry((definition,))
    permission = ToolPermission(
        "fixture",
        "fixture-v1",
        "approval_required" if approval else "allow",
        BudgetAmount(calls=1, bytes=100, cost=Decimal("0.01")),
        BudgetAmount(calls=daily_calls, bytes=1000, cost=Decimal(1)),
        BudgetAmount(calls=generation_calls, bytes=1000, cost=Decimal(1)),
    )
    return ToolRuntime(
        ToolRepository(base.database, registry), registry, ToolPolicy({definition.name: permission})
    )


@pytest.fixture
def runtime(tools: ToolFixture) -> RuntimeFixture:
    simulator = Simulator()
    return RuntimeFixture(tools, configured(tools, simulator), simulator)


async def reservations(base: ToolFixture) -> list[BudgetReservation]:
    async with base.database() as session:
        return list(
            await session.scalars(
                select(BudgetReservation).where(BudgetReservation.owner_id == base.owner)
            )
        )


async def test_dispatch_once_persistent_result_and_private_snapshot(
    runtime: RuntimeFixture,
) -> None:
    base, service = runtime.base, runtime.runtime
    request = runtime.request()
    results = await asyncio.gather(*[service.execute(base.owner, request, INPUT) for _ in range(5)])
    assert len(runtime.simulator.calls) == 1
    assert {r.result_digest for r in results} == {results[0].result_digest}
    await service.execute(base.owner, request, INPUT)
    snapshot = await service.repository.public_snapshot(base.owner, request.id)
    assert snapshot.run.state == "succeeded" and snapshot.latestResult is not None
    assert "synthetic question" not in snapshot.model_dump_json()
    ledger = await reservations(base)
    assert len(ledger) == 1 and ledger[0].state == "accounted" and ledger[0].measured is None
    run = await service.repository.get_run(base.owner, request.id)
    assert run.execution_id and run.dispatched_at and run.policy_snapshot


@pytest.mark.parametrize("decision", ["approve", "deny"])
async def test_approval_bound_idempotent_and_explicit_resume(
    runtime: RuntimeFixture, decision: str
) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, approval=True)
    request = runtime.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(base.owner, request, INPUT)
    assert not runtime.simulator.calls and not await reservations(base)
    approval = await service.repository.approval_required(base.owner, request.id, service.policy)
    request_id = uuid4()
    for _ in range(2):
        grant = await service.repository.decide(
            base.owner,
            approval.id,
            request_id,
            approval.input_digest,
            decision,
            policy=service.policy,
        )
        assert grant.state == ("approved" if decision == "approve" else "denied")
    if decision == "approve":
        await service.execute(base.owner, request, INPUT)
        assert len(runtime.simulator.calls) == 1
    else:
        with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
            await service.execute(base.owner, request, INPUT)


async def test_approval_owner_digest_expiry_and_policy_revocation(runtime: RuntimeFixture) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, approval=True)
    request = runtime.request()
    with pytest.raises(ToolError):
        await service.execute(base.owner, request, INPUT)
    approval = await service.repository.approval_required(base.owner, request.id, service.policy)
    for owner, digest, expected in [
        (uuid4(), approval.input_digest, "TOOL_NOT_FOUND"),
        (base.owner, "f" * 64, "TOOL_CONFLICT"),
    ]:
        with pytest.raises(ToolError, match=expected):
            await service.repository.decide(
                owner, approval.id, uuid4(), digest, "approve", policy=service.policy
            )
    with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
        await service.repository.decide(
            base.owner, approval.id, uuid4(), approval.input_digest, "approve", policy=ToolPolicy()
        )
    async with base.database() as session, session.begin():
        await session.execute(
            update(ToolApproval)
            .where(ToolApproval.id == approval.id)
            .values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
                created_at=datetime.now(UTC) - timedelta(seconds=5),
            )
        )
    with pytest.raises(ToolError, match="APPROVAL_EXPIRED"):
        await service.repository.decide(
            base.owner,
            approval.id,
            uuid4(),
            approval.input_digest,
            "approve",
            policy=service.policy,
        )
    assert not runtime.simulator.calls


@pytest.mark.parametrize("daily,generation", [(1, 10), (10, 1)])
async def test_concurrent_budget_reservations_fail_closed(
    runtime: RuntimeFixture, daily: int, generation: int
) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, daily_calls=daily, generation_calls=generation)
    outcomes = await asyncio.gather(
        *[service.execute(base.owner, runtime.request(f"step{i}"), INPUT) for i in range(3)],
        return_exceptions=True,
    )
    assert sum(isinstance(r, ToolError) and r.code == "BUDGET_LIMIT" for r in outcomes) == 2
    assert len(runtime.simulator.calls) == 1
    assert len(await reservations(base)) == 1


@pytest.mark.parametrize("idempotent", [True, False])
async def test_timeout_and_unknown_keep_conservative_budget(
    runtime: RuntimeFixture, idempotent: bool
) -> None:
    base = runtime.base
    runtime.simulator.wait = True
    service = configured(base, runtime.simulator, idempotent=idempotent, timeout=0.15)
    request = runtime.request()
    code = "TOOL_TIMEOUT" if idempotent else "PROVIDER_OUTCOME_UNKNOWN"
    with pytest.raises(ToolError, match=code):
        await service.execute(base.owner, request, INPUT)
    run = await service.repository.get_run(base.owner, request.id)
    assert run.state == ("timed_out" if idempotent else "outcome_unknown")
    assert runtime.simulator.closed
    assert (await reservations(base))[0].state == ("accounted" if idempotent else "unknown")
    with pytest.raises(ToolError):
        await service.execute(base.owner, request, INPUT)
    assert len(runtime.simulator.calls) == 1


async def test_retry_has_separate_reservation_and_bounded_attempt(runtime: RuntimeFixture) -> None:
    runtime.simulator.error = "retry"
    service = configured(runtime.base, runtime.simulator, retries=1)
    request = runtime.request()
    await service.execute(runtime.base.owner, request, INPUT)
    assert len(runtime.simulator.calls) == 2
    assert {r.attempt for r in await reservations(runtime.base)} == {1, 2}
    assert (await service.repository.get_run(runtime.base.owner, request.id)).attempt == 2


async def test_retry_rechecks_budget(runtime: RuntimeFixture) -> None:
    runtime.simulator.error = "retry"
    service = configured(runtime.base, runtime.simulator, retries=1, daily_calls=1)
    with pytest.raises(ToolError, match="BUDGET_LIMIT"):
        await service.execute(runtime.base.owner, runtime.request(), INPUT)
    assert len(runtime.simulator.calls) == 1


@pytest.mark.parametrize("change", ["cancel", "archive", "delete", "generation"])
async def test_live_cancellation_closes_handler_prevents_success(
    runtime: RuntimeFixture, change: str
) -> None:
    base, service = runtime.base, runtime.runtime
    runtime.simulator.wait = True
    request = runtime.request()
    task = asyncio.create_task(service.execute(base.owner, request, INPUT))
    await asyncio.wait_for(runtime.simulator.entered.wait(), 2)
    if change == "cancel":
        await service.cancel(base.owner, base.generation)
    else:
        async with base.database() as session, session.begin():
            if change == "generation":
                await session.execute(
                    update(ChatGeneration)
                    .where(ChatGeneration.id == base.generation)
                    .values(status="cancelled")
                )
            else:
                await session.execute(
                    update(ChatConversation)
                    .where(ChatConversation.id == base.conversation)
                    .values(
                        **{
                            ("archived_at" if change == "archive" else "deleted_at"): datetime.now(
                                UTC
                            )
                        }
                    )
                )
    with pytest.raises(ToolError, match="TOOL_CANCELLED"):
        await asyncio.wait_for(task, 2)
    assert runtime.simulator.closed
    async with base.database() as session:
        run = await session.get(ToolRun, request.id)
        assert run is not None and run.state == "cancelled"


async def test_input_conflict_and_cross_owner_never_dispatch(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    request = runtime.request()
    await service.execute(base.owner, request, INPUT)
    with pytest.raises(ToolError, match="TOOL_CONFLICT"):
        await service.execute(base.owner, request, b'{"query":"changed","language":"de"}')
    with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
        await service.execute(uuid4(), request, INPUT)
    assert len(runtime.simulator.calls) == 1


async def test_safe_error_does_not_publish_exception(runtime: RuntimeFixture) -> None:
    runtime.simulator.error = "private"
    request = runtime.request()
    with pytest.raises(ToolError, match="PROVIDER_ERROR"):
        await runtime.runtime.execute(runtime.base.owner, request, INPUT)
    snapshot = await runtime.runtime.repository.public_snapshot(runtime.base.owner, request.id)
    assert snapshot.errorCode == "PROVIDER_ERROR"
    assert "secret" not in snapshot.model_dump_json()


@pytest.mark.parametrize("dispatched,idempotent", [(False, True), (True, True), (True, False)])
async def test_restart_recovery_never_redispatches(
    runtime: RuntimeFixture, dispatched: bool, idempotent: bool
) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, idempotent=idempotent)
    request = runtime.request()
    await service.repository.create_run(base.owner, request, INPUT)
    run = await service.repository.claim(base.owner, request.id, service.policy)
    if dispatched:
        assert run.execution_id is not None
        await service.repository.dispatch(base.owner, run.id, run.execution_id, service.policy)
    async with base.database() as session, session.begin():
        await session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == base.conversation)
            .values(archived_at=datetime.now(UTC))
        )
    await service.repository.recover(base.owner)
    run = await service.repository.get_run(base.owner, request.id)
    assert run.state == ("outcome_unknown" if dispatched and not idempotent else "interrupted")
    ledger = await reservations(base)
    assert ledger[0].state == (
        "released" if not dispatched else "unknown" if not idempotent else "accounted"
    )
    assert not runtime.simulator.calls


async def test_text_ledger_day_rollover_restart_and_duplicate(
    runtime: RuntimeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = runtime.base
    budget = BudgetCoordinator(base.database)
    day = datetime(2026, 10, 13, 23, 59, tzinfo=UTC)
    monkeypatch.setattr("noris_ai.tools.budget.utc_now", lambda: day)
    await budget.reserve_text(base.owner, "phase1", "a" * 64, 60, 100)
    await budget.dispatch_text(base.owner, "phase1")
    await BudgetCoordinator(base.database).recover_text(base.owner)
    with pytest.raises(ToolError, match="BUDGET_LIMIT"):
        await budget.reserve_text(base.owner, "phase2", "b" * 64, 60, 100)
    day += timedelta(minutes=2)
    await budget.reserve_text(base.owner, "phase2", "b" * 64, 60, 100)
    with pytest.raises(ToolError, match="TOOL_CONFLICT"):
        await budget.reserve_text(base.owner, "phase1", "a" * 64, 60, 100)
    async with base.database() as session:
        days = list(await session.scalars(select(BudgetDay)))
        assert len(days) == 2 and all(d.tokens == 60 for d in days)


async def test_text_undispatched_recovery_releases_only_unused(runtime: RuntimeFixture) -> None:
    budget = BudgetCoordinator(runtime.base.database)
    owner = runtime.base.owner
    await budget.reserve_text(owner, "unused", "a" * 64, 100, 100)
    await budget.recover_text(owner)
    await budget.reserve_text(owner, "next", "b" * 64, 100, 100)
    assert {r.state for r in await reservations(runtime.base)} == {"reserved", "released"}


async def test_gateway_chat_title_and_continuation_reserve_exactly_once(
    runtime: RuntimeFixture, llm_config: Settings
) -> None:
    base = runtime.base
    config = llm_config.model_copy(update={"chat_owner_id": base.owner})
    provider = TitleProvider("Docker DNS-Probleme")
    budget = BudgetCoordinator(base.database)
    gateway = LLMGateway(config, provider, budget)
    first = ChatRequest(
        generationId="main-phase",
        conversationId="synthetic-chat",
        inputMessageId="input",
        modelId="fixture-alpha",
        attempt=1,
        messages=[LLMMessage(role="user", content="Docker DNS")],
    )
    await gateway.reserve(first)
    events = [event async for event in gateway.events(first)]
    assert events[-1] is not None and events[-1].type == "response.completed"
    await gateway.abandon(first.generationId)  # Manager/SSE cleanup must not count again.
    await gateway.conversation_title(
        ConversationTitleRequest(
            conversationId="synthetic-chat",
            inputMessageId="input",
            modelId="fixture-alpha",
            firstMessage="Docker DNS",
        )
    )
    provider.output = " additional details"
    continuation = first.model_copy(
        update={
            "generationId": "continuation-phase",
            "operation": "continue",
            "continuationCount": 1,
            "messages": [
                LLMMessage(role="user", content="Docker DNS"),
                LLMMessage(role="assistant", content="Docker DNS-Probleme"),
            ],
        }
    )
    await gateway.reserve(continuation)
    _ = [event async for event in gateway.events(continuation)]
    rows = await reservations(base)
    assert len(rows) == 3 and {r.phase_key for r in rows} == {
        "main-phase",
        "title:synthetic-chat",
        "continuation-phase",
    }
    assert all(r.calls == 1 and r.state == "accounted" and r.measured is None for r in rows)
    async with base.database() as session:
        day = await session.scalar(select(BudgetDay).where(BudgetDay.bucket == "text"))
        assert day is not None and day.tokens == sum(r.tokens for r in rows)
    restarted = LLMGateway(config, provider, BudgetCoordinator(base.database))
    with pytest.raises(LLMError, match="bereits"):
        await restarted.reserve(first)
    assert len(provider.calls) == 3


async def test_gateway_restart_budget_and_model_validation_before_provider(
    runtime: RuntimeFixture, llm_config: Settings
) -> None:
    base = runtime.base
    provider = TitleProvider()
    config = llm_config.model_copy(update={"chat_owner_id": base.owner})
    request = ChatRequest(
        generationId="phase",
        conversationId="chat",
        inputMessageId="input",
        modelId="fixture-alpha",
        attempt=1,
        messages=[LLMMessage(role="user", content="Hallo")],
    )
    gateway = LLMGateway(config, provider, BudgetCoordinator(base.database))
    await gateway.reserve(request)
    _ = [event async for event in gateway.events(request)]
    charged = (await reservations(base))[0].tokens
    restarted = LLMGateway(
        config.model_copy(update={"llm_daily_token_budget": charged}),
        provider,
        BudgetCoordinator(base.database),
    )
    with pytest.raises(LLMError) as limited:
        await restarted.reserve(request.model_copy(update={"generationId": "next"}))
    assert limited.value.code == "BUDGET_LIMIT" and len(provider.calls) == 1
    with pytest.raises(LLMError) as unavailable:
        await restarted.reserve(
            request.model_copy(update={"generationId": "wrong", "modelId": "not-approved"})
        )
    assert unavailable.value.code == "MODEL_UNAVAILABLE"
    assert len(await reservations(base)) == 1


async def test_child_cancel_and_commit_fence(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    parent = runtime.request("parent")
    child = runtime.request("child").model_copy(
        update={"parent_run_id": parent.id, "deadline_at": parent.deadline_at}
    )
    await service.repository.create_run(base.owner, parent, INPUT)
    await service.repository.create_run(base.owner, child, INPUT)
    claimed = await service.repository.claim(base.owner, child.id, service.policy)
    assert claimed.execution_id is not None
    await service.repository.dispatch(base.owner, child.id, claimed.execution_id, service.policy)
    await service.cancel(base.owner, base.generation, root_id=parent.id)
    from tests.integration.test_tool_foundation import OUTPUT

    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await service.repository.complete(
            base.owner, child.id, OUTPUT, execution_id=claimed.execution_id
        )
    assert (await service.repository.get_run(base.owner, parent.id)).state == "cancelled"
    assert (await service.repository.get_run(base.owner, child.id)).cancel_requested_at is not None


async def test_worker_fencing_cannot_finish_another_claim(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    request = runtime.request()
    await service.repository.create_run(base.owner, request, INPUT)
    claimed = await service.repository.claim(base.owner, request.id, service.policy)
    await service.repository.finalize(
        base.owner, request.id, "failed", "PROVIDER_ERROR", execution_id=uuid4()
    )
    assert (await service.repository.get_run(base.owner, request.id)).state == "running"
    from tests.integration.test_tool_foundation import OUTPUT

    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await service.repository.complete(base.owner, request.id, OUTPUT, execution_id=uuid4())
    await service.repository.finalize(
        base.owner, request.id, "interrupted", "TOOL_INTERRUPTED", execution_id=claimed.execution_id
    )


async def test_pending_deadline_and_recovery_expire_grants(runtime: RuntimeFixture) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, approval=True)
    request = runtime.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(base.owner, request, INPUT)
    async with base.database() as session, session.begin():
        await session.execute(
            update(ToolRun)
            .where(ToolRun.id == request.id)
            .values(deadline_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    await service.repository.expire_pending(base.owner)
    assert (await service.repository.get_run(base.owner, request.id)).state == "timed_out"
    await service.repository.recover(base.owner)
    async with base.database() as session:
        approval = await session.scalar(
            select(ToolApproval).where(ToolApproval.run_id == request.id)
        )
        assert approval is not None and approval.state == "expired"


async def test_shutdown_interrupts_and_cannot_accept_new_work(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    runtime.simulator.wait = True
    request = runtime.request()
    task = asyncio.create_task(service.execute(base.owner, request, INPUT))
    await asyncio.wait_for(runtime.simulator.entered.wait(), 2)
    await asyncio.wait_for(service.close(), 2)
    with pytest.raises(ToolError, match="TOOL_INTERRUPTED"):
        await task
    assert runtime.simulator.closed
    assert (await service.repository.get_run(base.owner, request.id)).state == "interrupted"
    with pytest.raises(ToolError, match="TOOL_INTERRUPTED"):
        await service.execute(base.owner, runtime.request("new"), INPUT)


async def test_api_persistent_snapshot_approval_origin_and_owner(
    runtime: RuntimeFixture, llm_config: Settings
) -> None:
    base = runtime.base
    service = configured(base, runtime.simulator, approval=True)
    request = runtime.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(base.owner, request, INPUT)
    approval = await service.repository.approval_required(base.owner, request.id, service.policy)
    app: FastAPI = create_app(llm_config)
    app.state.chat_settings = llm_config.model_copy(update={"chat_owner_id": base.owner})
    app.state.chat_service = ChatService(ChatRepository(base.database))
    app.state.tool_runtime = service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", auth=AUTH
    ) as client:
        response = await client.get(f"/api/v1/chat/tool-runs/{request.id}")
        assert (
            response.status_code == 200 and response.json()["run"]["state"] == "awaiting_approval"
        )
        assert response.json()["approval"]["id"] == str(approval.id)
        assert "synthetic question" not in response.text
        decision = {
            "requestId": str(uuid4()),
            "inputDigest": approval.input_digest,
            "decision": "approve",
        }
        denied = await client.post(
            f"/api/v1/chat/tool-approvals/{approval.id}/decision",
            json=decision,
            headers={"Origin": "https://evil.example"},
        )
        assert denied.status_code == 403
        response = await client.post(
            f"/api/v1/chat/tool-approvals/{approval.id}/decision", json=decision
        )
        assert response.status_code == 200 and response.json()["state"] == "approved"
        await service.execute(base.owner, request, INPUT)
        snapshot = await client.get(f"/api/v1/chat/tool-runs/{request.id}")
        assert snapshot.json()["run"]["state"] == "succeeded"
        assert snapshot.json()["latestResult"]["provider"] == "searxng"
        assert runtime.simulator.calls[0].approval_id == approval.id
        app.state.chat_settings = llm_config.model_copy(update={"chat_owner_id": uuid4()})
        assert (await client.get(f"/api/v1/chat/tool-runs/{request.id}")).status_code == 404
        assert (
            await client.post(f"/api/v1/chat/tool-approvals/{approval.id}/decision", json=decision)
        ).status_code == 404


async def test_policy_change_between_claim_dispatch_and_commit_denied(
    runtime: RuntimeFixture,
) -> None:
    base, service = runtime.base, runtime.runtime
    request = runtime.request()
    await service.repository.create_run(base.owner, request, INPUT)
    run = await service.repository.claim(base.owner, request.id, service.policy)
    assert run.execution_id is not None
    permission = service.policy.permissions[request.tool_id]
    changed = ToolPolicy(
        {
            request.tool_id: replace(
                permission, per_call=BudgetAmount(calls=1, bytes=100, cost=Decimal("0.02"))
            )
        }
    )
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        await service.repository.dispatch(base.owner, request.id, run.execution_id, changed)
    from tests.integration.test_tool_foundation import OUTPUT

    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        await service.repository.complete(
            base.owner, request.id, OUTPUT, execution_id=run.execution_id, policy=changed
        )
    assert not runtime.simulator.calls
    assert (await reservations(base))[0].state == "reserved"


async def test_effective_deadline_is_enforced_at_dispatch_and_commit(
    runtime: RuntimeFixture,
) -> None:
    base, service = runtime.base, runtime.runtime
    request = runtime.request()
    await service.repository.create_run(base.owner, request, INPUT)
    run = await service.repository.claim(base.owner, request.id, service.policy)
    assert run.execution_id is not None
    async with base.database() as session, session.begin():
        await session.execute(
            update(ToolRun)
            .where(ToolRun.id == request.id)
            .values(execution_deadline_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with pytest.raises(ToolError, match="TOOL_TIMEOUT"):
        await service.repository.dispatch(base.owner, request.id, run.execution_id, service.policy)
    from tests.integration.test_tool_foundation import OUTPUT

    with pytest.raises(ToolError, match="TOOL_TIMEOUT"):
        await service.repository.complete(
            base.owner, request.id, OUTPUT, execution_id=run.execution_id, policy=service.policy
        )


async def test_child_cannot_extend_parent_execution_deadline(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    parent = runtime.request("parent")
    await service.repository.create_run(base.owner, parent, INPUT)
    parent_run = await service.repository.claim(base.owner, parent.id, service.policy)
    child = runtime.request("child").model_copy(
        update={
            "parent_run_id": parent.id,
            "deadline_at": parent.deadline_at,
        }
    )
    await service.repository.create_run(base.owner, child, INPUT)
    child_run = await service.repository.claim(base.owner, child.id, service.policy)
    assert child_run.execution_deadline_at == parent_run.execution_deadline_at


async def test_second_runtime_cannot_finalize_the_active_execution(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    runtime.simulator.wait = True
    request = runtime.request()
    task = asyncio.create_task(service.execute(base.owner, request, INPUT))
    await asyncio.wait_for(runtime.simulator.entered.wait(), 2)
    second = configured(base, runtime.simulator)
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await second.execute(base.owner, request, INPUT)
    assert (await service.repository.get_run(base.owner, request.id)).state == "running"
    runtime.simulator.release.set()
    await asyncio.wait_for(task, 2)
    assert len(runtime.simulator.calls) == 1


async def test_blocked_admission_has_bounded_safe_storage_error(runtime: RuntimeFixture) -> None:
    base, service = runtime.base, runtime.runtime
    async with base.database() as blocker, blocker.begin():
        await blocker.execute(
            select(ChatConversation)
            .where(ChatConversation.id == base.conversation)
            .with_for_update()
        )
        with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
            await asyncio.wait_for(service.execute(base.owner, runtime.request(), INPUT), 2.5)
    assert not runtime.simulator.calls and not await reservations(base)


async def test_cancel_at_result_commit_is_cancelled_and_preserves_budget(
    runtime: RuntimeFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, service = runtime.base, runtime.runtime
    complete = service.repository.complete

    async def stop_before_commit(
        owner: UUID,
        run_id: UUID,
        payload: bytes,
        *,
        execution_id: UUID | None = None,
        policy: ToolPolicy | None = None,
    ) -> ToolResult:
        await service.cancel(owner, base.generation)
        return await complete(owner, run_id, payload, execution_id=execution_id, policy=policy)

    monkeypatch.setattr(service.repository, "complete", stop_before_commit)
    request = runtime.request()
    with pytest.raises(ToolError, match="TOOL_CANCELLED"):
        await service.execute(base.owner, request, INPUT)
    assert (await service.repository.get_run(base.owner, request.id)).state == "cancelled"
    assert await service.repository.get_result(base.owner, request.id) is None
    assert (await reservations(base))[0].state == "accounted"
