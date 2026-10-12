"""Short, owner-scoped transactions; no dispatch, network or policy bypass."""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.models import ChatConversation, ChatGeneration
from noris_ai.chat.repository import ModelDatabase, utc_now
from noris_ai.tools.errors import ToolError, ToolErrorCode
from noris_ai.tools.models import ToolResult, ToolRun
from noris_ai.tools.registry import ToolRegistry, canonical_payload, payload_digest
from noris_ai.tools.schemas import (
    TERMINAL_STATES,
    ToolRunCreate,
    ToolRunState,
    check_transition,
)


class ToolRepository:
    def __init__(self, database: ModelDatabase, registry: ToolRegistry) -> None:
        self._database = database
        self._registry = registry

    async def _scope(
        self,
        session: AsyncSession,
        owner_id: UUID,
        conversation_id: UUID,
        generation_id: UUID,
        *,
        write: bool,
    ) -> ChatGeneration:
        # Same lock order as ChatRepository: conversation -> generation -> run.
        query = select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.owner_id == owner_id,
            ChatConversation.deleted_at.is_(None),
        )
        conversation = await session.scalar(query.with_for_update() if write else query)
        if conversation is None or (write and conversation.archived_at is not None):
            raise ToolError("TOOL_NOT_FOUND")
        generation_query = select(ChatGeneration).where(
            ChatGeneration.id == generation_id,
            ChatGeneration.owner_id == owner_id,
            ChatGeneration.conversation_id == conversation_id,
        )
        generation = await session.scalar(
            generation_query.with_for_update() if write else generation_query
        )
        if generation is None:
            raise ToolError("TOOL_NOT_FOUND")
        return generation

    async def _run(
        self,
        session: AsyncSession,
        owner_id: UUID,
        run_id: UUID,
        *,
        write: bool,
    ) -> tuple[ToolRun, ChatGeneration]:
        run = await session.scalar(
            select(ToolRun).where(
                ToolRun.id == run_id,
                ToolRun.owner_id == owner_id,
            )
        )
        if run is None:
            raise ToolError("TOOL_NOT_FOUND")
        generation = await self._scope(
            session,
            owner_id,
            run.conversation_id,
            run.generation_id,
            write=write,
        )
        if write:
            # Re-read after acquiring the scope locks: another transaction may have finished it.
            run = await session.scalar(
                select(ToolRun)
                .where(ToolRun.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if run is None:
                raise ToolError("TOOL_NOT_FOUND")
        return run, generation

    async def _live_parent(self, session: AsyncSession, run: ToolRun) -> None:
        if run.parent_run_id is not None:
            parent = await session.get(ToolRun, run.parent_run_id)
            if parent is None or parent.state in TERMINAL_STATES or parent.cancel_requested_at:
                raise ToolError("TOOL_STATE_CONFLICT")

    async def create_run(
        self,
        owner_id: UUID,
        request: ToolRunCreate,
        payload: bytes,
    ) -> tuple[ToolRun, bool]:
        definition = self._registry.get(request.tool_id)
        value = definition.validate_input(payload, request.invocation_kind)
        normalized = canonical_payload(value)
        digest = payload_digest(normalized)
        if request.provider_key != definition.provider_key:
            raise ToolError("TOOL_FORBIDDEN")
        if (request.provider_key is None) != (request.config_version is None):
            raise ToolError("TOOL_INPUT_INVALID")
        async with self._database() as session, session.begin():
            generation = await self._scope(
                session,
                owner_id,
                request.conversation_id,
                request.generation_id,
                write=True,
            )
            existing = await session.scalar(
                select(ToolRun).where(
                    ToolRun.generation_id == request.generation_id,
                    ToolRun.step_key == request.step_key,
                )
            )
            if existing is not None:
                if any(
                    (
                        existing.id != request.id,
                        existing.owner_id != owner_id,
                        existing.tool_id != request.tool_id,
                        existing.input_digest != digest,
                        existing.invocation_kind != request.invocation_kind,
                        existing.parent_run_id != request.parent_run_id,
                        existing.provider_key != request.provider_key,
                        existing.config_version != request.config_version,
                        existing.deadline_at != request.deadline_at,
                    )
                ):
                    raise ToolError("TOOL_CONFLICT")
                return existing, False
            if await session.get(ToolRun, request.id) is not None:
                # Do not disclose which owner/conversation already holds this ID.
                raise ToolError("TOOL_CONFLICT")
            if generation.status not in ("queued", "running"):
                raise ToolError("TOOL_STATE_CONFLICT")
            if request.deadline_at <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            run = ToolRun(
                **request.model_dump(exclude={"tool_id"}),
                owner_id=owner_id,
                tool_id=definition.name,
                schema_version=definition.schema_version,
                input=value.model_dump(mode="json"),
                input_digest=digest,
            )
            if request.parent_run_id is not None:
                parent = await session.scalar(
                    select(ToolRun).where(
                        ToolRun.id == request.parent_run_id,
                        ToolRun.owner_id == owner_id,
                        ToolRun.conversation_id == request.conversation_id,
                        ToolRun.generation_id == request.generation_id,
                    )
                )
                if parent is None:
                    raise ToolError("TOOL_NOT_FOUND")
                if request.deadline_at > parent.deadline_at:
                    raise ToolError("TOOL_INPUT_INVALID")
                await self._live_parent(session, run)
            session.add(run)
            await session.flush()
            return run, True

    async def get_run(self, owner_id: UUID, run_id: UUID) -> ToolRun:
        async with self._database() as session:
            run, _ = await self._run(session, owner_id, run_id, write=False)
            return run

    async def get_result(self, owner_id: UUID, run_id: UUID) -> ToolResult | None:
        async with self._database() as session:
            await self._run(session, owner_id, run_id, write=False)
            return await session.scalar(
                select(ToolResult)
                .where(ToolResult.run_id == run_id)
                .order_by(ToolResult.result_version.desc())
                .limit(1)
            )

    async def transition(
        self,
        owner_id: UUID,
        run_id: UUID,
        expected: ToolRunState,
        target: ToolRunState,
        *,
        error_code: ToolErrorCode | None = None,
    ) -> ToolRun:
        # Success is only legal through the atomic validated-result transaction below.
        if target == "succeeded":
            raise ToolError("TOOL_STATE_CONFLICT")
        check_transition(expected, target)
        async with self._database() as session, session.begin():
            run, generation = await self._run(session, owner_id, run_id, write=True)
            if run.state != expected:
                raise ToolError("TOOL_STATE_CONFLICT")
            now = utc_now()
            if target in ("running", "awaiting_approval"):
                if generation.status not in ("queued", "running") or run.cancel_requested_at:
                    raise ToolError("TOOL_STATE_CONFLICT")
                if run.deadline_at <= now:
                    raise ToolError("TOOL_TIMEOUT")
                await self._live_parent(session, run)
            run.state = target
            run.error_code = error_code
            if target == "running":
                run.started_at = now
            if target in TERMINAL_STATES:
                run.finished_at = now
            if target == "cancelled":
                run.cancel_requested_at = now
            await session.flush()
            return run

    async def complete(self, owner_id: UUID, run_id: UUID, payload: bytes) -> ToolResult:
        async with self._database() as session, session.begin():
            run, generation = await self._run(session, owner_id, run_id, write=True)
            definition = self._registry.get(run.tool_id)
            value = definition.validate_output(payload)
            digest = payload_digest(canonical_payload(value))
            if run.state == "succeeded":
                result = await session.get(ToolResult, (run_id, 1))
                if result is not None and result.result_digest == digest:
                    return result
                raise ToolError("TOOL_CONFLICT")
            check_transition(cast(ToolRunState, run.state), "succeeded")
            if generation.status not in ("queued", "running") or run.cancel_requested_at:
                raise ToolError("TOOL_STATE_CONFLICT")
            await self._live_parent(session, run)
            if run.deadline_at <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            result = ToolResult(
                run_id=run_id,
                result_version=1,
                output_schema=definition.name,
                output=value.model_dump(mode="json"),
                result_digest=digest,
            )
            session.add(result)
            run.state = "succeeded"
            run.finished_at = utc_now()
            await session.flush()
            return result
