"""P2 atomic outbox/replay using P1b's deterministic handlers and PostgreSQL."""

# pyright: reportPrivateUsage=false

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatGeneration, ChatMessage, ChatStreamEvent
from noris_ai.chat.replay import replay
from noris_ai.chat.repository import ChatRepository
from noris_ai.tools.errors import ToolError
from noris_ai.tools.events import ToolEventType, ToolSnapshotEvent
from noris_ai.tools.models import ToolResult, ToolRun
from tests.integration import test_tool_runtime as runtime_cases
from tests.integration.test_tool_foundation import INPUT, OUTPUT
from tests.integration.test_tool_runtime import RuntimeFixture, configured

tool_schema = runtime_cases.tool_schema
tools = runtime_cases.tools
runtime = runtime_cases.runtime
pytestmark = pytest.mark.integration


@pytest.fixture
async def events(runtime: RuntimeFixture) -> RuntimeFixture:
    base = runtime.base
    async with base.database() as session, session.begin():
        generation = await session.get(ChatGeneration, base.generation)
        assert generation is not None
        message = ChatMessage(
            id=uuid4(),
            conversation_id=base.conversation,
            parent_message_id=generation.input_message_id,
            generation_id=base.generation,
            role="assistant",
            content="",
            status="streaming",
        )
        session.add(message)
        await session.flush()
        generation.assistant_message_id = message.id
    return runtime


async def stored(events: RuntimeFixture) -> list[ChatStreamEvent]:
    return list(
        await ChatRepository(events.base.database).list_stream_events(events.base.generation)
    )


async def resumed(
    events: RuntimeFixture,
    *,
    after: int = 0,
    initial: bool = True,
    capacity: int = 256,
    owner: UUID | None = None,
    include_tools: bool = True,
):
    return await replay(
        events.base.database,
        owner or events.base.owner,
        events.base.generation,
        after,
        capacity,
        events.runtime.repository,
        include_tools=include_tools,
        initial=initial,
    )


def snapshot(batch: list[dict[str, object]]) -> ToolSnapshotEvent:
    return ToolSnapshotEvent.model_validate_json(json.dumps(batch[0]))


async def test_offline_completion_and_idempotent_terminal(events: RuntimeFixture) -> None:
    request = events.request()
    for _ in range(2):
        await events.runtime.execute(events.base.owner, request, INPUT)
    rows = await stored(events)
    assert [row.event_type for row in rows] == [
        "tool.progress",
        "tool.started",
        "tool.result",
        "tool.completed",
    ]
    assert [row.sequence for row in rows] == [1, 2, 3, 4]
    assert len(events.simulator.calls) == 1
    batch, sequence = await resumed(events)
    assert sequence == 4
    assert batch[0]["type"] == "tool.snapshot"
    assert snapshot(batch).runs[0].state == "succeeded"
    result = snapshot(batch).runs[0].result
    assert result is not None and result.sourceCount == 0
    assert "synthetic question" not in str(batch) and "config_version" not in str(batch)
    assert "sources" not in str(batch) and "policy_snapshot" not in str(batch)


async def test_result_outbox_failure_rolls_back_everything(
    events: RuntimeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, base = events.runtime, events.base
    request = events.request()
    await service.repository.create_run(base.owner, request, INPUT)
    run = await service.repository.claim(base.owner, request.id, service.policy)
    original = service.repository._event

    async def fail(
        session: AsyncSession,
        generation: ChatGeneration,
        run: ToolRun,
        kind: ToolEventType | None = None,
    ) -> None:
        await original(session, generation, run, kind)
        raise SQLAlchemyError("synthetic outbox failure")

    with monkeypatch.context() as patch:
        patch.setattr(service.repository, "_event", fail)
        with pytest.raises(SQLAlchemyError):
            await service.repository.complete(
                base.owner, run.id, OUTPUT, execution_id=run.execution_id, policy=service.policy
            )
    async with base.database() as session:
        assert await session.get(ToolResult, (run.id, 1)) is None
    saved = await service.repository.get_run(base.owner, run.id)
    assert saved.state == "running" and saved.event_sequence == 2
    assert len(await stored(events)) == 2
    await service.repository.complete(
        base.owner, run.id, OUTPUT, execution_id=run.execution_id, policy=service.policy
    )
    assert [row.sequence for row in await stored(events)] == [1, 2, 3, 4]


async def test_concurrent_chat_and_tool_writes_share_sequence(events: RuntimeFixture) -> None:
    base = events.base
    repository = ChatRepository(base.database)
    payload: dict[str, object] = {
        "version": 1,
        "type": "chat.generation.delta",
        "seq": 1,
        "generationId": str(base.generation),
        "conversationId": str(base.conversation),
        "delta": "x",
    }
    await asyncio.gather(
        repository.persist_generation_event(base.generation, payload, "x"),
        *(
            events.runtime.repository.create_run(base.owner, events.request(f"step-{i}"), INPUT)
            for i in range(8)
        ),
    )
    rows = await stored(events)
    assert [row.sequence for row in rows] == list(range(1, 10))
    assert all(row.payload["seq"] == row.sequence for row in rows)
    generation = await repository.get_generation(base.owner, base.generation)
    assert generation.last_sequence == 9


async def test_approval_snapshot_and_idempotent_decision(events: RuntimeFixture) -> None:
    service = configured(events.base, events.simulator, approval=True)
    events.runtime = service
    request = events.request()
    with pytest.raises(ToolError, match="APPROVAL_REQUIRED"):
        await service.execute(events.base.owner, request, INPUT)
    approval = await service.repository.approval_required(
        events.base.owner, request.id, service.policy
    )
    batch, _ = await resumed(events)
    grant = snapshot(batch).runs[0].approval
    assert grant is not None and grant.approvalId == approval.id and grant.state == "pending"
    decision = uuid4()
    for _ in range(2):
        await service.repository.decide(
            events.base.owner,
            approval.id,
            decision,
            approval.input_digest,
            "approve",
            policy=service.policy,
        )
    assert len(await stored(events)) == 3 and not events.simulator.calls
    batch, _ = await resumed(events)
    grant = snapshot(batch).runs[0].approval
    assert grant is not None and grant.state == "approved"
    await service.execute(events.base.owner, request, INPUT)
    assert len(events.simulator.calls) == 1


@pytest.mark.parametrize("state", ["queued", "awaiting_approval", "running"])
async def test_offline_repeated_cancel(events: RuntimeFixture, state: str) -> None:
    service = configured(events.base, events.simulator, approval=state == "awaiting_approval")
    events.runtime = service
    request = events.request()
    await service.repository.create_run(events.base.owner, request, INPUT)
    task = None
    if state == "running":
        events.simulator.wait = True
        task = asyncio.create_task(service.execute(events.base.owner, request, INPUT))
        await events.simulator.entered.wait()
    elif state == "awaiting_approval":
        await service.repository.approval_required(events.base.owner, request.id, service.policy)
    for _ in range(2):
        await service.cancel(events.base.owner, events.base.generation)
    if task:
        with pytest.raises(ToolError, match="TOOL_CANCELLED"):
            await task
    rows = await stored(events)
    assert sum(row.event_type == "tool.cancelled" for row in rows) == 1
    batch, _ = await resumed(events)
    assert snapshot(batch).runs[0].state == "cancelled"


async def test_timeout_and_safe_error(events: RuntimeFixture) -> None:
    service = configured(events.base, events.simulator, timeout=0.05)
    events.runtime = service
    events.simulator.wait = True
    with pytest.raises(ToolError, match="TOOL_TIMEOUT"):
        await service.execute(events.base.owner, events.request(), INPUT)
    assert (await stored(events))[-1].event_type == "tool.timed_out"
    service = configured(events.base, events.simulator)
    events.runtime = service
    events.simulator.wait, events.simulator.error = False, "private"
    with pytest.raises(ToolError, match="PROVIDER_ERROR"):
        await service.execute(events.base.owner, events.request("failure"), INPUT)
    batch, _ = await resumed(events)
    assert "secret provider body" not in str(batch)
    assert (await stored(events))[-1].event_type == "tool.failed"


@pytest.mark.parametrize("cancel", [False, True])
async def test_restart_recovers_fence_without_publisher(
    events: RuntimeFixture, cancel: bool
) -> None:
    request = events.request()
    service, base = events.runtime, events.base
    await service.repository.create_run(base.owner, request, INPUT)
    await service.repository.claim(base.owner, request.id, service.policy)
    if cancel:
        await service.repository.cancel_runs(base.owner, base.generation)
    await service.repository.recover(base.owner)
    await service.repository.recover(base.owner)
    await ChatRepository(base.database).mark_running_generations_interrupted(base.owner)
    batch, _ = await resumed(events)
    assert snapshot(batch).runs[0].state == ("cancelled" if cancel else "interrupted")
    assert not events.simulator.calls
    assert (
        sum(row.event_type in ("tool.cancelled", "tool.failed") for row in await stored(events))
        == 1
    )


async def test_retention_reload_and_owner_isolation(events: RuntimeFixture) -> None:
    base = events.base
    await events.runtime.execute(base.owner, events.request(), INPUT)
    async with base.database() as session, session.begin():
        await session.execute(
            update(ChatGeneration)
            .where(ChatGeneration.id == base.generation)
            .values(status="completed", completed_at=datetime.now(UTC) - timedelta(days=7))
        )
    await ChatRepository(base.database).prune_stream_events(24)
    assert not await stored(events)
    batch, sequence = await resumed(events)
    assert sequence == 4 and snapshot(batch).runs[0].state == "succeeded"
    assert batch[-1]["type"] == "chat.resume.snapshot"
    with pytest.raises(ChatError) as rejected:
        await resumed(events, owner=uuid4())
    assert rejected.value.code == "GENERATION_NOT_FOUND"


async def test_legacy_client_and_overflow_use_chat_snapshot(events: RuntimeFixture) -> None:
    await events.runtime.execute(events.base.owner, events.request(), INPUT)
    batch, _ = await resumed(events, include_tools=False)
    assert [value["type"] for value in batch] == ["chat.resume.snapshot"]
    batch, _ = await resumed(events, capacity=2)
    assert [value["type"] for value in batch] == ["tool.snapshot", "chat.resume.snapshot"]


async def test_late_completion_cannot_undo_cancel(events: RuntimeFixture) -> None:
    request = events.request()
    service, base = events.runtime, events.base
    await service.repository.create_run(base.owner, request, INPUT)
    run = await service.repository.claim(base.owner, request.id, service.policy)
    await service.repository.cancel_runs(base.owner, base.generation)
    with pytest.raises(ToolError):
        await service.repository.complete(base.owner, run.id, OUTPUT, execution_id=run.execution_id)
    await service.repository.recover(base.owner)
    assert (await stored(events))[-1].event_type == "tool.cancelled"


async def test_new_runs_are_bounded(
    events: RuntimeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("noris_ai.tools.repository.MAX_GENERATION_TOOL_RUNS", 1)
    await events.runtime.repository.create_run(events.base.owner, events.request(), INPUT)
    with pytest.raises(ToolError, match="BUDGET_LIMIT"):
        await events.runtime.repository.create_run(
            events.base.owner, events.request("second"), INPUT
        )
    assert len(await stored(events)) == 1


async def test_missing_tail_recovers_terminal_projection(events: RuntimeFixture) -> None:
    await events.runtime.execute(events.base.owner, events.request(), INPUT)
    async with events.base.database() as session, session.begin():
        await session.execute(
            delete(ChatStreamEvent).where(
                ChatStreamEvent.generation_id == events.base.generation,
                ChatStreamEvent.sequence == 4,
            )
        )
    batch, sequence = await resumed(events, initial=False)
    assert sequence == 4 and snapshot(batch).runs[0].state == "succeeded"
    assert batch[-1]["type"] == "chat.resume.snapshot"
