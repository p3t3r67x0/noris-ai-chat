"""P1a transactions and security boundaries against disposable PostgreSQL."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, event, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapper

from noris_ai.chat.models import ChatConversation, ChatGeneration, ChatMessage
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolApproval, ToolResult, ToolRun
from noris_ai.tools.registry import ToolRegistry, create_tool_registry
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.schemas import ToolRunCreate

pytestmark = pytest.mark.integration
INPUT = b'{"query":"synthetic question","language":"de"}'
OUTPUT = json.dumps(
    {
        "sources": [],
        "warnings": [],
        "provider": "searxng",
        "config_version": "fixture-v1",
        "fetched_at": "2026-10-12T10:00:00Z",
        "partial": False,
    }
).encode()


@dataclass(frozen=True)
class ToolFixture:
    repository: ToolRepository
    database: async_sessionmaker[AsyncSession]
    owner: UUID
    conversation: UUID
    generation: UUID

    def request(self, step: str = "search", *, parent: UUID | None = None) -> ToolRunCreate:
        return ToolRunCreate(
            id=uuid4(),
            conversation_id=self.conversation,
            generation_id=self.generation,
            tool_id="web.search.v1",
            step_key=step,
            invocation_kind="web_mode",
            parent_run_id=parent,
            deadline_at=datetime.now(UTC) + timedelta(minutes=1),
        )


@pytest.fixture
def tool_schema(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")


@pytest.fixture
async def tools(tool_schema: None) -> AsyncGenerator[ToolFixture]:
    engine = create_async_engine(os.environ["NORIS_TEST_DATABASE_URL"])
    database = async_sessionmaker(engine, expire_on_commit=False)
    owner, conversation, generation, message = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        async with database() as session, session.begin():
            session.add(
                ChatConversation(
                    id=conversation,
                    owner_id=owner,
                    title="Synthetic tools",
                    title_source="manual",
                    version=1,
                )
            )
            await session.flush()
            session.add(
                ChatMessage(
                    id=message,
                    conversation_id=conversation,
                    role="user",
                    content="Synthetic question",
                    status="completed",
                )
            )
            await session.flush()
            session.add(
                ChatGeneration(
                    id=generation,
                    conversation_id=conversation,
                    owner_id=owner,
                    input_message_id=message,
                    model_id="fixture",
                    status="running",
                )
            )
        yield ToolFixture(
            ToolRepository(database, create_tool_registry()),
            database,
            owner,
            conversation,
            generation,
        )
    finally:
        await engine.dispose()


async def test_concurrent_creation_and_result_replay_are_idempotent(tools: ToolFixture) -> None:
    request = tools.request()
    outcomes = await asyncio.gather(
        *[tools.repository.create_run(tools.owner, request, INPUT) for _ in range(4)]
    )
    assert sum(created for _, created in outcomes) == 1
    assert {run.id for run, _ in outcomes} == {request.id}
    await tools.repository.transition(tools.owner, request.id, "queued", "running")
    results = await asyncio.gather(
        *[tools.repository.complete(tools.owner, request.id, OUTPUT) for _ in range(4)]
    )
    assert len({result.result_digest for result in results}) == 1
    persisted = await ToolRepository(tools.database, create_tool_registry()).get_result(
        tools.owner, request.id
    )
    assert persisted is not None and persisted.output["sources"] == []
    assert (await tools.repository.get_run(tools.owner, request.id)).state == "succeeded"
    async with tools.database() as session:
        assert len((await session.scalars(select(ToolResult))).all()) == 1


async def test_conflicting_input_step_and_id_rejected(tools: ToolFixture) -> None:
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    for candidate, payload in (
        (request, b'{"query":"different question","language":"de"}'),
        (request.model_copy(update={"id": uuid4()}), INPUT),
        (request.model_copy(update={"step_key": "different-step"}), INPUT),
    ):
        with pytest.raises(ToolError, match="TOOL_CONFLICT"):
            await tools.repository.create_run(tools.owner, candidate, payload)


async def test_foreign_owner_hidden_and_archived_deleted_chats_denied(tools: ToolFixture) -> None:
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
        await tools.repository.create_run(uuid4(), tools.request("foreign"), INPUT)
    for read in (tools.repository.get_run, tools.repository.get_result):
        with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
            await read(uuid4(), request.id)
    async with tools.database() as session, session.begin():
        await session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == tools.conversation)
            .values(archived_at=datetime.now(UTC))
        )
    assert (await tools.repository.get_run(tools.owner, request.id)).state == "queued"
    with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
        await tools.repository.transition(tools.owner, request.id, "queued", "running")
    async with tools.database() as session, session.begin():
        await session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == tools.conversation)
            .values(deleted_at=datetime.now(UTC))
        )
    for read in (tools.repository.get_run, tools.repository.get_result):
        with pytest.raises(ToolError, match="TOOL_NOT_FOUND"):
            await read(tools.owner, request.id)


async def test_invalid_result_and_failed_insert_preserve_running_state(tools: ToolFixture) -> None:
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await tools.repository.transition(tools.owner, request.id, "queued", "succeeded")
    await tools.repository.transition(tools.owner, request.id, "queued", "running")
    with pytest.raises(ToolError, match="TOOL_OUTPUT_INVALID"):
        await tools.repository.complete(tools.owner, request.id, b"{}")

    def violate_result_constraint(
        mapper: Mapper[ToolResult], connection: Connection, result: ToolResult
    ) -> None:
        result.result_version = 0

    event.listen(ToolResult, "before_insert", violate_result_constraint)
    try:
        with pytest.raises(IntegrityError):
            await tools.repository.complete(tools.owner, request.id, OUTPUT)
    finally:
        event.remove(ToolResult, "before_insert", violate_result_constraint)
    assert (await tools.repository.get_run(tools.owner, request.id)).state == "running"
    assert await tools.repository.get_result(tools.owner, request.id) is None
    await tools.repository.complete(tools.owner, request.id, OUTPUT)
    with pytest.raises(ToolError, match="TOOL_CONFLICT"):
        await tools.repository.complete(tools.owner, request.id, OUTPUT.replace(b"false", b"true"))


async def test_cancel_before_commit_prevents_result_and_restart(tools: ToolFixture) -> None:
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    await tools.repository.transition(tools.owner, request.id, "queued", "running")
    await tools.repository.transition(tools.owner, request.id, "running", "cancelled")
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await tools.repository.complete(tools.owner, request.id, OUTPUT)
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await tools.repository.transition(tools.owner, request.id, "queued", "running")
    assert await tools.repository.get_result(tools.owner, request.id) is None
    run = await tools.repository.get_run(tools.owner, request.id)
    assert run.cancel_requested_at is not None and run.finished_at is not None


async def test_concurrent_cancel_and_complete_have_one_terminal_outcome(tools: ToolFixture) -> None:
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    await tools.repository.transition(tools.owner, request.id, "queued", "running")
    outcomes = await asyncio.gather(
        tools.repository.transition(tools.owner, request.id, "running", "cancelled"),
        tools.repository.complete(tools.owner, request.id, OUTPUT),
        return_exceptions=True,
    )
    assert sum(isinstance(outcome, ToolError) for outcome in outcomes) == 1
    run = await tools.repository.get_run(tools.owner, request.id)
    result = await tools.repository.get_result(tools.owner, request.id)
    assert run.state in ("succeeded", "cancelled")
    assert (result is not None) == (run.state == "succeeded")


async def test_parent_and_generation_terminal_states_stop_children(tools: ToolFixture) -> None:
    parent = tools.request("parent")
    await tools.repository.create_run(tools.owner, parent, INPUT)
    child = tools.request("child", parent=parent.id).model_copy(
        update={"deadline_at": parent.deadline_at}
    )
    await tools.repository.create_run(tools.owner, child, INPUT)
    await tools.repository.transition(tools.owner, child.id, "queued", "running")
    await tools.repository.transition(tools.owner, parent.id, "queued", "cancelled")
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await tools.repository.complete(tools.owner, child.id, OUTPUT)
    async with tools.database() as session, session.begin():
        await session.execute(
            update(ChatGeneration)
            .where(ChatGeneration.id == tools.generation)
            .values(status="cancelled")
        )
    with pytest.raises(ToolError, match="TOOL_STATE_CONFLICT"):
        await tools.repository.create_run(tools.owner, tools.request("later"), INPUT)


async def test_deadline_and_unregistered_provider_denied(tools: ToolFixture) -> None:
    with pytest.raises(ToolError, match="TOOL_TIMEOUT"):
        await tools.repository.create_run(
            tools.owner,
            tools.request().model_copy(
                update={"deadline_at": datetime.now(UTC) - timedelta(seconds=1)}
            ),
            INPUT,
        )
    with pytest.raises(ToolError, match="TOOL_FORBIDDEN"):
        await tools.repository.create_run(
            tools.owner,
            tools.request().model_copy(
                update={"provider_key": "arbitrary", "config_version": "v1"}
            ),
            INPUT,
        )
    request = tools.request()
    await tools.repository.create_run(tools.owner, request, INPUT)
    await tools.repository.transition(tools.owner, request.id, "queued", "running")
    async with tools.database() as session, session.begin():
        await session.execute(
            update(ToolRun)
            .where(ToolRun.id == request.id)
            .values(deadline_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with pytest.raises(ToolError, match="TOOL_TIMEOUT"):
        await tools.repository.complete(tools.owner, request.id, OUTPUT)
    await tools.repository.transition(
        tools.owner, request.id, "running", "timed_out", error_code="TOOL_TIMEOUT"
    )
    assert (await tools.repository.get_run(tools.owner, request.id)).error_code == "TOOL_TIMEOUT"


async def test_database_rejects_cross_owner_generation_and_parent(tools: ToolFixture) -> None:
    request = tools.request()
    run, _ = await tools.repository.create_run(tools.owner, request, INPUT)
    for changes in ({"owner_id": uuid4()}, {"generation_id": uuid4()}, {"parent_run_id": run.id}):
        async with tools.database() as session, session.begin():
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(
                        update(ToolRun).where(ToolRun.id == run.id).values(**changes)
                    )


async def test_database_payloads_are_bounded(tools: ToolFixture) -> None:
    run, _ = await tools.repository.create_run(tools.owner, tools.request(), INPUT)
    async with tools.database() as session, session.begin():
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    update(ToolRun)
                    .where(ToolRun.id == run.id)
                    .values(input={"large": "x" * 65_536})
                )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    ToolResult(
                        run_id=run.id,
                        result_version=1,
                        output_schema="web.search.v1",
                        output={"large": "x" * 262_144},
                        result_digest="a" * 64,
                    )
                )
                await session.flush()


async def test_approval_bound_to_owner_digest_and_provider(tools: ToolFixture) -> None:
    definition = replace(create_tool_registry().get("web.search.v1"), provider_key="fixture")
    repository = ToolRepository(tools.database, ToolRegistry((definition,)))
    request = tools.request().model_copy(update={"provider_key": "fixture", "config_version": "v1"})
    run, _ = await repository.create_run(tools.owner, request, INPUT)
    fields: dict[str, object] = dict(
        owner_id=tools.owner,
        run_id=run.id,
        input_digest=run.input_digest,
        provider_key="fixture",
        config_version="v1",
        permission_scope="web_search",
        max_calls=1,
        max_cost=Decimal("0.01"),
        currency="EUR",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    async with tools.database() as session, session.begin():
        session.add(ToolApproval(**fields))
        await session.flush()
        for changes in (
            {"owner_id": uuid4()},
            {"input_digest": "f" * 64},
            {"provider_key": "other"},
        ):
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(ToolApproval(**(fields | changes)))
                    await session.flush()


async def test_application_role_cannot_update_result_payload(tools: ToolFixture) -> None:
    async with tools.database() as session:
        exists = await session.scalar(
            text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname='noris_app')")
        )
        if not exists:
            pytest.fail("Create the non-superuser noris_app role using postgres-init.sh")
        assert await session.scalar(
            text("SELECT has_table_privilege('noris_app', 'chat_tool_run', 'INSERT')")
        )
        assert await session.scalar(
            text("SELECT has_table_privilege('noris_app', 'chat_tool_result', 'INSERT')")
        )
        assert not await session.scalar(
            text("SELECT has_table_privilege('noris_app', 'chat_tool_result', 'UPDATE')")
        )
