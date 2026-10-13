"""Real SearXNG handler + loopback HTTP + disposable PostgreSQL + P2 replay."""

# pyright: reportPrivateUsage=false

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.models import ChatConversation, ChatGeneration
from noris_ai.chat.replay import replay
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.service import ChatService
from noris_ai.core.config import Settings
from noris_ai.main import create_app
from noris_ai.tools.budget import BudgetAmount, BudgetReservation
from noris_ai.tools.errors import ToolError
from noris_ai.tools.events import ToolEventType, ToolSnapshotEvent
from noris_ai.tools.models import ToolApproval, ToolResult, ToolRun
from noris_ai.tools.policy import ToolPermission, ToolPolicy
from noris_ai.tools.providers.searxng import SearXNGProvider
from noris_ai.tools.registry import canonical_payload, create_tool_registry
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.runtime import ToolRuntime
from noris_ai.tools.schemas import SearchInput, SearchResult, ToolRunCreate
from tests.fixtures.searxng_http import SearchServer
from tests.integration import test_tool_foundation as foundation
from tests.integration.test_tool_foundation import ToolFixture
from tests.llm_integration.http_server import serve
from tests.llm_integration.test_http_search import config
from tests.unit.test_llm_api import AUTH

tool_schema = foundation.tool_schema
tools = foundation.tools
pytestmark = pytest.mark.integration


def policy(
    *, approval: bool = False, calls: int = 100, version: str = "http-fixture"
) -> ToolPolicy:
    return ToolPolicy(
        {
            "web.search.v1": ToolPermission(
                "searxng",
                version,
                "approval_required" if approval else "allow",
                BudgetAmount(calls=1, bytes=65_536),
                BudgetAmount(calls=calls, bytes=65_536 * calls),
                BudgetAmount(calls=calls, bytes=65_536 * calls),
            )
        }
    )


@dataclass
class SearchFixture:
    base: ToolFixture
    server: SearchServer
    provider: SearXNGProvider
    runtime: ToolRuntime

    def request(self, step: str = "search") -> ToolRunCreate:
        return self.base.request(step).model_copy(
            update={"provider_key": "searxng", "config_version": "http-fixture"}
        )

    async def replay(self) -> ToolSnapshotEvent:
        batch, _ = await replay(
            self.base.database,
            self.base.owner,
            self.base.generation,
            0,
            256,
            self.runtime.repository,
            include_tools=True,
            initial=True,
            tools_only=True,
        )
        return ToolSnapshotEvent.model_validate_json(json.dumps(batch[0]))


PAYLOAD = canonical_payload(SearchInput(query="æøå ÄÖÜ search", language="de"))


@pytest.fixture
async def search(tools: ToolFixture) -> AsyncIterator[SearchFixture]:
    server = SearchServer()
    async with serve(server.app) as url, SearXNGProvider(config(url)) as provider:
        registry = create_tool_registry(provider)
        runtime = ToolRuntime(ToolRepository(tools.database, registry), registry, policy())
        try:
            yield SearchFixture(tools, server, provider, runtime)
        finally:
            await runtime.close()


async def test_full_search_commit_reservation_events_replay_and_idempotency(
    search: SearchFixture,
) -> None:
    service, base = search.runtime, search.base
    request = search.request()
    results = await asyncio.gather(
        *(service.execute(base.owner, request, PAYLOAD) for _ in range(6))
    )
    assert search.server.calls == 1

    assert len({result.result_digest for result in results}) == 1
    saved = await service.repository.public_snapshot(base.owner, request.id)
    assert saved.run.state == "succeeded" and isinstance(saved.latestResult, SearchResult)
    assert len(saved.latestResult.sources) == 5
    assert saved.latestResult.sources[0].title == "Quelle"
    assert "Ignore previous instructions" in saved.latestResult.sources[0].snippet
    async with base.database() as session:
        reservation = await session.scalar(
            select(BudgetReservation).where(BudgetReservation.run_id == request.id)
        )
        assert reservation is not None and reservation.state == "accounted"
        assert reservation.calls == 1 and reservation.bytes == 65_536
    events = await ChatRepository(base.database).list_stream_events(base.generation)
    assert [event.event_type for event in events] == [
        "tool.progress",
        "tool.started",
        "tool.result",
        "tool.completed",
    ]
    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert "Ignore previous" not in str([event.payload for event in events])
    restarted = ToolRuntime(service.repository, service.registry, service.policy)
    try:
        for _ in range(3):
            assert (await search.replay()).runs[0].state == "succeeded"
            await restarted.execute(base.owner, request, PAYLOAD)
    finally:
        await restarted.close()
    assert search.server.calls == 1


@pytest.mark.parametrize("unicode_output", [False, True])
async def test_utf8_limits_survive_dispatch_commit_snapshot_and_replay(
    search: SearchFixture, unicode_output: bool
) -> None:
    search.server.unicode_content = unicode_output
    payload = canonical_payload(
        SearchInput(query="unicode-result" if unicode_output else "🌍" * 1000, language="de")
    )
    request = search.request()
    await search.runtime.execute(search.base.owner, request, payload)
    snapshot = await search.runtime.repository.public_snapshot(search.base.owner, request.id)
    assert snapshot.run.state == "succeeded" and isinstance(snapshot.latestResult, SearchResult)
    assert len(canonical_payload(snapshot.latestResult)) <= 65_536
    assert len(snapshot.latestResult.sources) == (8 if unicode_output else 5)
    assert (await search.replay()).runs[0].state == "succeeded"
    await search.runtime.execute(search.base.owner, request, payload)
    assert search.server.calls == 1


@pytest.mark.parametrize(
    "kind,state,code",
    [
        ("error", "failed", "PROVIDER_ERROR"),
        ("timeout", "timed_out", "TOOL_TIMEOUT"),
        ("cancel", "cancelled", "TOOL_CANCELLED"),
        ("shutdown", "interrupted", "TOOL_INTERRUPTED"),
        ("generation", "cancelled", "TOOL_CANCELLED"),
        ("generation_completed", "cancelled", "TOOL_CANCELLED"),
    ],
)
async def test_http_terminal_is_replayable_and_closes_io(
    search: SearchFixture, kind: str, state: str, code: str
) -> None:
    request = search.request()
    if kind == "timeout":
        request = request.model_copy(
            update={"deadline_at": datetime.now(UTC) + timedelta(seconds=0.5)}
        )
    search.server.wait = kind not in {"error", "timeout"}
    payload = canonical_payload(SearchInput(query=f"/p6-{kind}", language="en"))
    task = asyncio.create_task(search.runtime.execute(search.base.owner, request, payload))
    await asyncio.wait_for(search.server.entered.wait(), 5)
    if kind != "error":
        assert (await search.replay()).runs[0].state == "running"
    if kind == "cancel":
        for _ in range(2):
            await search.runtime.cancel(search.base.owner, search.base.generation)
    elif kind == "shutdown":
        await search.runtime.close()
    elif kind in {"generation", "generation_completed"}:
        async with search.base.database() as session, session.begin():
            await session.execute(
                update(ChatGeneration)
                .where(ChatGeneration.id == search.base.generation)
                .values(status="completed" if kind == "generation_completed" else "cancelled")
            )
    with pytest.raises(ToolError, match=code):
        await task
    await asyncio.wait_for(search.server.closed.wait(), 5)
    assert (await search.replay()).runs[0].state == state
    assert await search.runtime.repository.get_result(search.base.owner, request.id) is None
    assert search.server.calls == 1


@pytest.mark.parametrize(
    "case",
    [
        "default",
        "deny",
        "approval",
        "version",
        "provider",
        "owner",
        "generation",
        "parent",
        "deadline",
        "budget",
    ],
)
async def test_admission_never_calls_provider_without_authority(
    search: SearchFixture, case: str
) -> None:
    service, base = search.runtime, search.base
    request = search.request()
    owner = base.owner
    expected = "TOOL_FORBIDDEN"
    permission = service.policy.permissions["web.search.v1"]
    if case == "default":
        service.policy, expected = ToolPolicy(), "TOOL_UNAVAILABLE"
    elif case == "deny":
        service.policy = ToolPolicy({"web.search.v1": replace(permission, decision="deny")})
    elif case == "approval":
        service.policy, expected = policy(approval=True), "APPROVAL_REQUIRED"
    elif case == "version":
        request = request.model_copy(update={"config_version": "stale"})
    elif case == "provider":
        request = request.model_copy(update={"provider_key": "brave"})
    elif case == "owner":
        owner, expected = uuid4(), "TOOL_NOT_FOUND"
    elif case in {"generation", "parent"}:
        request = request.model_copy(
            update={"generation_id" if case == "generation" else "parent_run_id": uuid4()}
        )
        expected = "TOOL_NOT_FOUND"
    elif case == "deadline":
        request = request.model_copy(
            update={"deadline_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
        expected = "TOOL_TIMEOUT"
    elif case == "budget":
        service.policy = ToolPolicy(
            {"web.search.v1": replace(permission, per_call=BudgetAmount(calls=1, bytes=100))}
        )
        expected = "BUDGET_LIMIT"
    with pytest.raises(ToolError, match=expected):
        await service.execute(owner, request, PAYLOAD)
    assert search.server.calls == 0


async def test_explicit_approval_and_concurrent_budget(search: SearchFixture) -> None:
    service, base = search.runtime, search.base
    service.policy = policy(approval=True, calls=1)
    request = search.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(base.owner, request, PAYLOAD)
    approval = await service.repository.approval_required(base.owner, request.id, service.policy)
    await service.repository.decide(
        base.owner, approval.id, uuid4(), approval.input_digest, "approve", policy=service.policy
    )
    await service.execute(base.owner, request, PAYLOAD)
    service.policy = policy(calls=1)
    results = await asyncio.gather(
        *(service.execute(base.owner, search.request(f"next-{i}"), PAYLOAD) for i in range(3)),
        return_exceptions=True,
    )
    assert all(
        isinstance(result, ToolError) and result.code == "BUDGET_LIMIT" for result in results
    )
    assert search.server.calls == 1


async def test_expired_approval_never_dispatches(search: SearchFixture) -> None:
    service, base = search.runtime, search.base
    service.policy = policy(approval=True)
    request = search.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(base.owner, request, PAYLOAD)
    approval = await service.repository.approval_required(base.owner, request.id, service.policy)
    await service.repository.decide(
        base.owner, approval.id, uuid4(), approval.input_digest, "approve", policy=service.policy
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
        await service.execute(base.owner, request, PAYLOAD)
    assert search.server.calls == 0


async def test_parent_cancel_closes_real_child_search(search: SearchFixture) -> None:
    parent = search.request("parent")
    await search.runtime.repository.create_run(search.base.owner, parent, PAYLOAD)
    child = search.request("child").model_copy(
        update={"parent_run_id": parent.id, "deadline_at": parent.deadline_at}
    )
    search.server.wait = True
    task = asyncio.create_task(search.runtime.execute(search.base.owner, child, PAYLOAD))
    await asyncio.wait_for(search.server.entered.wait(), 5)
    await search.runtime.cancel(search.base.owner, search.base.generation, root_id=parent.id)
    with pytest.raises(ToolError, match="TOOL_CANCELLED"):
        await task
    await asyncio.wait_for(search.server.closed.wait(), 5)
    assert {run.state for run in (await search.replay()).runs} == {"cancelled"}


async def test_stop_after_claim_before_http_dispatch(
    search: SearchFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = search.runtime.repository.dispatch

    async def stop(*args: object, **kwargs: object):
        await search.runtime.cancel(search.base.owner, search.base.generation)
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(search.runtime.repository, "dispatch", stop)
    with pytest.raises(ToolError, match="TOOL_CANCELLED"):
        await search.runtime.execute(search.base.owner, search.request(), PAYLOAD)
    assert search.server.calls == 0


async def test_config_mismatch_between_policy_and_bound_provider(search: SearchFixture) -> None:
    search.runtime.policy = policy(version="different")
    request = search.request().model_copy(update={"config_version": "different"})
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        await search.runtime.execute(search.base.owner, request, PAYLOAD)
    assert search.server.calls == 0


@pytest.mark.parametrize("boundary", ["dispatch", "commit"])
@pytest.mark.parametrize("change", ["version", "policy"])
async def test_configuration_and_policy_changes_keep_execution_binding(
    search: SearchFixture, boundary: str, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = getattr(
        search.runtime.repository, "dispatch" if boundary == "dispatch" else "complete"
    )

    async def changed(*args: object, **kwargs: object):
        permission = search.runtime.policy.permissions["web.search.v1"]
        search.runtime.policy = ToolPolicy(
            {
                "web.search.v1": replace(
                    permission,
                    **(
                        {"config_version": "changed"}
                        if change == "version"
                        else {"decision": "deny"}
                    ),
                )
            }
        )
        # Both methods accept the current policy as a named argument.
        if boundary == "dispatch":
            return await original(*args[:3], search.runtime.policy)
        return await original(*args, **{**kwargs, "policy": search.runtime.policy})

    monkeypatch.setattr(
        search.runtime.repository, "dispatch" if boundary == "dispatch" else "complete", changed
    )
    request = search.request()
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        await search.runtime.execute(search.base.owner, request, PAYLOAD)
    assert search.server.calls == int(boundary == "commit")
    assert await search.runtime.repository.get_result(search.base.owner, request.id) is None


async def test_separate_workers_cannot_dispatch_or_finalize_same_run(search: SearchFixture) -> None:
    service, base = search.runtime, search.base
    search.server.wait = True
    request = search.request()
    task = asyncio.create_task(service.execute(base.owner, request, PAYLOAD))
    await asyncio.wait_for(search.server.entered.wait(), 5)
    other = ToolRuntime(service.repository, service.registry, service.policy)
    try:
        with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
            await other.execute(base.owner, request, PAYLOAD)
        assert (await service.repository.get_run(base.owner, request.id)).state == "running"
        search.server.release.set()
        await task
    finally:
        await other.close()
    assert search.server.calls == 1


async def test_competing_searches_share_existing_budget(search: SearchFixture) -> None:
    search.runtime.policy = policy(calls=1)
    search.server.wait = True
    tasks = [
        asyncio.create_task(
            search.runtime.execute(search.base.owner, search.request(f"compete-{i}"), PAYLOAD)
        )
        for i in range(2)
    ]
    await asyncio.wait_for(search.server.entered.wait(), 5)
    search.server.release.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert (
        sum(isinstance(result, ToolError) and result.code == "BUDGET_LIMIT" for result in results)
        == 1
    )
    assert search.server.calls == 1


async def test_restart_after_dispatch_preserves_fence_and_never_repeats_search(
    search: SearchFixture,
) -> None:
    service, base = search.runtime, search.base
    request = search.request()
    await service.repository.create_run(base.owner, request, PAYLOAD)
    claimed = await service.repository.claim(base.owner, request.id, service.policy)
    assert claimed.execution_id is not None
    await service.repository.dispatch(base.owner, request.id, claimed.execution_id, service.policy)
    await service.repository.recover(base.owner)
    assert (await search.replay()).runs[0].state == "interrupted"
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await service.execute(base.owner, request, PAYLOAD)
    assert search.server.calls == 0


async def test_cancel_immediately_before_result_commit(
    search: SearchFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = search.runtime.repository.complete

    async def cancel_then_commit(*args: object, **kwargs: object):
        await search.runtime.cancel(search.base.owner, search.base.generation)
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(search.runtime.repository, "complete", cancel_then_commit)
    request = search.request()
    with pytest.raises(ToolError, match="TOOL_CANCELLED"):
        await search.runtime.execute(search.base.owner, request, PAYLOAD)
    assert (await search.replay()).runs[0].state == "cancelled"
    assert await search.runtime.repository.get_result(search.base.owner, request.id) is None


async def test_search_outbox_rollback_is_atomic(
    search: SearchFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = search.runtime.repository._event

    async def fail(
        session: AsyncSession,
        generation: ChatGeneration,
        run: ToolRun,
        kind: ToolEventType | None = None,
    ) -> None:
        await original(session, generation, run, kind)
        if kind == "tool.result":
            raise SQLAlchemyError("controlled outbox rollback")

    monkeypatch.setattr(search.runtime.repository, "_event", fail)
    request = search.request()
    with pytest.raises(ToolError, match="TOOL_UNAVAILABLE"):
        await search.runtime.execute(search.base.owner, request, PAYLOAD)
    async with search.base.database() as session:
        assert await session.get(ToolResult, (request.id, 1)) is None
    events = await ChatRepository(search.base.database).list_stream_events(search.base.generation)
    assert not any(event.event_type in {"tool.result", "tool.completed"} for event in events)


@pytest.mark.parametrize("operation", ["caller", "shutdown"])
async def test_repeated_task_cancel_during_stream_cleanup_is_drained(
    search: SearchFixture, operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release, interrupted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = Response.aclose

    async def delayed_close(response: Response) -> None:
        entered.set()
        try:
            await release.wait()
            await original(response)
        except asyncio.CancelledError:
            interrupted.set()
            raise

    monkeypatch.setattr(Response, "aclose", delayed_close)
    search.server.wait = True
    request = search.request()
    task = asyncio.create_task(search.runtime.execute(search.base.owner, request, PAYLOAD))
    await asyncio.wait_for(search.server.entered.wait(), 5)
    closing = None
    try:
        if operation == "caller":
            task.cancel()
            target = task
        else:
            closing = asyncio.create_task(search.runtime.close())
            target = closing
        await asyncio.wait_for(entered.wait(), 5)
        target.cancel()
        # Let the second cancellation reach the cleanup await before releasing it.
        for _ in range(10):
            await asyncio.sleep(0)
        assert not interrupted.is_set()
        assert not target.done()
        target.cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not interrupted.is_set()
        assert not target.done()
    finally:
        release.set()
        await asyncio.gather(
            task, *([closing] if closing is not None else []), return_exceptions=True
        )
    await asyncio.wait_for(search.server.closed.wait(), 5)
    assert not search.runtime._active and not search.runtime._cancels
    assert not any(
        pending.get_coro().__qualname__ in {"invoke", "ToolRuntime._execute"}
        or pending.get_coro().__qualname__.startswith("ToolRuntime._execute.<locals>.")
        for pending in asyncio.all_tasks()
        if pending is not asyncio.current_task()
    )
    assert await search.runtime.repository.get_result(search.base.owner, request.id) is None
    assert (await search.runtime.repository.get_run(search.base.owner, request.id)).state in {
        "cancelled",
        "interrupted",
    }
    assert search.server.calls == 1


async def test_shutdown_waits_for_inflight_admission(
    search: SearchFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    original = search.runtime.repository.create_run

    async def delayed_create(*args: object, **kwargs: object):
        result = await original(*args, **kwargs)  # type: ignore[arg-type]
        entered.set()
        await release.wait()
        return result

    monkeypatch.setattr(search.runtime.repository, "create_run", delayed_create)
    request = search.request()
    task = asyncio.create_task(search.runtime.execute(search.base.owner, request, PAYLOAD))
    await asyncio.wait_for(entered.wait(), 5)
    closing = asyncio.create_task(search.runtime.close())
    try:
        for _ in range(10):
            await asyncio.sleep(0)
        assert not closing.done()
    finally:
        release.set()
        await closing
    with pytest.raises(ToolError, match="TOOL_INTERRUPTED"):
        await task
    assert not search.runtime._active and not search.runtime._cancels
    assert (
        await search.runtime.repository.get_run(search.base.owner, request.id)
    ).state == "interrupted"
    assert search.server.calls == 0


async def test_changed_execution_fence_cannot_commit_result(
    search: SearchFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = search.runtime.repository.complete

    async def fenced_commit(*args: object, **kwargs: object):
        async with search.base.database() as session, session.begin():
            await session.execute(
                update(ToolRun).where(ToolRun.id == args[1]).values(execution_id=uuid4())
            )
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(search.runtime.repository, "complete", fenced_commit)
    request = search.request()
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await search.runtime.execute(search.base.owner, request, PAYLOAD)
    assert await search.runtime.repository.get_result(search.base.owner, request.id) is None
    assert search.server.calls == 1
    async with search.base.database() as session:
        reservation = await session.scalar(
            select(BudgetReservation).where(BudgetReservation.run_id == request.id)
        )
        assert reservation is not None and reservation.state == "dispatched"
    await search.runtime.repository.recover(search.base.owner)


async def test_authorized_existing_api_isolation_archive_and_soft_delete(
    search: SearchFixture, llm_config: Settings
) -> None:
    request = search.request()
    await search.runtime.execute(search.base.owner, request, PAYLOAD)
    app_config = llm_config.model_copy(update={"chat_owner_id": search.base.owner})
    app = create_app(app_config)
    app.state.chat_settings = app_config
    app.state.chat_service = ChatService(ChatRepository(search.base.database))
    app.state.tool_runtime = search.runtime
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        url = f"/api/v1/chat/tool-runs/{request.id}"
        assert (await client.get(url)).status_code == 401
        response = await client.get(url, auth=AUTH)
        assert (
            response.status_code == 200 and response.json()["latestResult"]["provider"] == "searxng"
        )
        assert (
            await client.post("/api/v1/chat/tools/execute", auth=AUTH, json={})
        ).status_code == 404
        with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
            await search.runtime.repository.public_snapshot(uuid4(), request.id)
        async with search.base.database() as session, session.begin():
            await session.execute(
                update(ChatConversation)
                .where(ChatConversation.id == search.base.conversation)
                .values(archived_at=datetime.now(UTC))
            )
        assert (await client.get(url, auth=AUTH)).status_code == 200
        with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
            await search.runtime.execute(search.base.owner, search.request("archived"), PAYLOAD)
        async with search.base.database() as session, session.begin():
            await session.execute(
                update(ChatConversation)
                .where(ChatConversation.id == search.base.conversation)
                .values(deleted_at=datetime.now(UTC))
            )
        assert (await client.get(url, auth=AUTH)).status_code == 404


async def test_controlled_latency_measurements(search: SearchFixture, tmp_path: Path) -> None:
    samples: dict[str, list[float]] = {
        "provider_ms": [],
        "run_ms": [],
        "commit_ms": [],
        "replay_read_ms": [],
        "cancel_ms": [],
    }
    original = search.runtime.repository.complete

    async def measured(*args: object, **kwargs: object):
        start = perf_counter()
        result = await original(*args, **kwargs)  # type: ignore[arg-type]
        samples["commit_ms"].append((perf_counter() - start) * 1000)
        return result

    search.runtime.repository.complete = measured  # type: ignore[method-assign]
    for i in range(10):
        start = perf_counter()
        await search.provider.search(SearchInput(query="measurement", language="en"))
        samples["provider_ms"].append((perf_counter() - start) * 1000)
        start = perf_counter()
        await search.runtime.execute(search.base.owner, search.request(f"measure-{i}"), PAYLOAD)
        samples["run_ms"].append((perf_counter() - start) * 1000)
        start = perf_counter()
        await search.replay()
        samples["replay_read_ms"].append((perf_counter() - start) * 1000)
    for i in range(5):
        search.server.wait = True
        search.server.entered.clear()
        search.server.closed.clear()
        task = asyncio.create_task(
            search.runtime.execute(search.base.owner, search.request(f"cancel-{i}"), PAYLOAD)
        )
        await asyncio.wait_for(search.server.entered.wait(), 5)
        start = perf_counter()
        await search.runtime.cancel(search.base.owner, search.base.generation)
        with pytest.raises(ToolError, match="TOOL_CANCELLED"):
            await task
        await asyncio.wait_for(search.server.closed.wait(), 5)
        samples["cancel_ms"].append((perf_counter() - start) * 1000)
    await asyncio.to_thread(
        (tmp_path / "performance.json").write_text, json.dumps(samples, indent=2)
    )
    print("P6_PERFORMANCE=" + json.dumps(samples))
