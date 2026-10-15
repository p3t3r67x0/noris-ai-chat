"""Short, owner-scoped transactions; no dispatch, network or policy bypass."""

import hashlib
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.models import ChatConversation, ChatGeneration
from noris_ai.chat.repository import ModelDatabase, utc_now
from noris_ai.chat.stream import append_event
from noris_ai.tools.api_schemas import ToolApprovalResponse, ToolRunResponse
from noris_ai.tools.budget import (
    DIMENSIONS,
    BudgetAmount,
    BudgetCoordinator,
    BudgetReservation,
    bound_transaction,
    lock_owner,
)
from noris_ai.tools.cancellation import GenerationToolContext
from noris_ai.tools.errors import ToolError, ToolErrorCode
from noris_ai.tools.events import (
    MAX_GENERATION_TOOL_RUNS,
    ToolApprovalProjection,
    ToolEvent,
    ToolEventType,
    ToolProjection,
    ToolResultReference,
)
from noris_ai.tools.models import ToolApproval, ToolResult, ToolRun
from noris_ai.tools.policy import ToolPolicy
from noris_ai.tools.registry import (
    RegisteredTool,
    ToolRegistry,
    canonical_payload,
    encode_payload,
    payload_digest,
)
from noris_ai.tools.schemas import (
    TERMINAL_STATES,
    ApprovalState,
    FetchInput,
    InvocationKind,
    SearchResult,
    SearchSource,
    SourceDocument,
    ToolRunCreate,
    ToolRunSnapshot,
    ToolRunState,
    check_transition,
    search_source_id,
)


class ToolRepository:
    def __init__(self, database: ModelDatabase, registry: ToolRegistry) -> None:
        self._database = database
        self._registry = registry

    async def projection(self, session: AsyncSession, run: ToolRun) -> ToolProjection:
        # Explicit allowlist, also during recovery: registry membership alone
        # does not permit a new tool or private schema onto the browser stream.
        if run.tool_id not in ("web.search.v1", "web.fetch.v1"):
            raise ToolError("TOOL_FORBIDDEN")
        definition = self._registry.get(run.tool_id)
        approval = await session.scalar(select(ToolApproval).where(ToolApproval.run_id == run.id))
        reference = None
        if run.state == "succeeded":
            result = await session.get(ToolResult, (run.id, 1))
            if result is None:
                raise ToolError("TOOL_OUTPUT_INVALID")
            output = definition.validate_output(encode_payload(result.output))
            reference = ToolResultReference(
                sourceCount=len(output.sources) if isinstance(output, SearchResult) else None
            )
        return ToolProjection(
            runId=run.id,
            toolId=run.tool_id,
            state=cast(ToolRunState, run.state),
            lastSequence=run.event_sequence,
            updatedAt=run.event_updated_at or run.finished_at or run.started_at or run.created_at,
            cancelRequested=run.cancel_requested_at is not None,
            result=reference,
            errorCode=cast(ToolErrorCode | None, run.error_code),
            approval=ToolApprovalProjection(
                approvalId=approval.id,
                inputDigest=approval.input_digest,
                state=cast(ApprovalState, approval.state),
                expiresAt=approval.expires_at,
            )
            if approval is not None and run.state == "awaiting_approval"
            else None,
        )

    async def _event(
        self,
        session: AsyncSession,
        generation: ChatGeneration,
        run: ToolRun,
        kind: ToolEventType | None = None,
    ) -> None:
        kinds: dict[str, ToolEventType] = {
            "queued": "tool.progress",
            "awaiting_approval": "tool.approval_required",
            "running": "tool.started",
            "succeeded": "tool.completed",
            "failed": "tool.failed",
            "cancelled": "tool.cancelled",
            "timed_out": "tool.timed_out",
            "interrupted": "tool.failed",
            "outcome_unknown": "tool.failed",
        }
        await session.flush()
        run.event_sequence = generation.last_sequence + 1
        run.event_updated_at = utc_now()
        projection = await self.projection(session, run)
        event = ToolEvent(
            type=kind or kinds[run.state],
            conversationId=run.conversation_id,
            generationId=run.generation_id,
            runId=run.id,
            seq=run.event_sequence,
            timestamp=projection.updatedAt,
            payload=projection,
        )
        append_event(session, generation, event.model_dump(mode="json"))

    async def _scope(
        self,
        session: AsyncSession,
        owner_id: UUID,
        conversation_id: UUID,
        generation_id: UUID,
        *,
        write: bool,
        finalizing: bool = False,
    ) -> ChatGeneration:
        if write:
            await bound_transaction(session)
        # Same lock order as ChatRepository: conversation -> generation -> run.
        query = select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.owner_id == owner_id,
        )
        if not finalizing:
            query = query.where(ChatConversation.deleted_at.is_(None))
        conversation = await session.scalar(query.with_for_update() if write else query)
        if conversation is None or (
            write and not finalizing and conversation.archived_at is not None
        ):
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
        finalizing: bool = False,
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
            finalizing=finalizing,
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

    async def _live_parent(self, session: AsyncSession, run: ToolRun) -> datetime | None:
        if run.parent_run_id is not None:
            parent = await session.get(ToolRun, run.parent_run_id)
            if parent is None or parent.state in TERMINAL_STATES or parent.cancel_requested_at:
                raise ToolError("TOOL_STATE_CONFLICT")
            deadline = min(parent.deadline_at, parent.execution_deadline_at or parent.deadline_at)
            if deadline <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            return deadline
        return None

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
                        existing.source_search_run_id != request.source_search_run_id,
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
            if (
                generation.status not in ("queued", "running")
                or generation.cancelled_at is not None
            ):
                raise ToolError("TOOL_STATE_CONFLICT")
            count = await session.scalar(
                select(func.count())
                .select_from(ToolRun)
                .where(ToolRun.generation_id == generation.id)
            )
            if count is not None and count >= MAX_GENERATION_TOOL_RUNS:
                raise ToolError("BUDGET_LIMIT")
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
            if isinstance(value, FetchInput):
                await self._search_source(session, run, value.source_id)
            elif run.source_search_run_id is not None:
                raise ToolError("TOOL_FORBIDDEN")
            session.add(run)
            await session.flush()
            await self._event(session, generation, run)
            return run, True

    async def get_run(self, owner_id: UUID, run_id: UUID) -> ToolRun:
        async with self._database() as session:
            run, _ = await self._run(session, owner_id, run_id, write=False)
            return run

    async def check_live(self, owner: UUID, run_id: UUID) -> None:
        async with self._database() as session:
            run, generation = await self._run(session, owner, run_id, write=False)
            conversation = await session.get(ChatConversation, run.conversation_id)
            if (
                run.cancel_requested_at
                or (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                )
                or conversation is None
                or conversation.archived_at is not None
            ):
                raise ToolError("TOOL_CANCELLED")
            await self._live_parent(session, run)

    async def get_result(self, owner_id: UUID, run_id: UUID) -> ToolResult | None:
        async with self._database() as session:
            await self._run(session, owner_id, run_id, write=False)
            return await session.scalar(
                select(ToolResult)
                .where(ToolResult.run_id == run_id)
                .order_by(ToolResult.result_version.desc())
                .limit(1)
            )

    async def research_result(
        self,
        owner: UUID,
        conversation: UUID,
        generation_id: UUID,
        run_id: UUID,
        tool_id: str,
        policy: ToolPolicy,
    ) -> SearchResult | SourceDocument:
        """Revalidate persisted provenance; the caller's in-memory output is not authority."""
        async with self._database() as session, session.begin():
            run, generation = await self._run(session, owner, run_id, write=True)
            definition = self._registry.get(tool_id)
            policy.require(definition, run)
            if (
                run.conversation_id != conversation
                or run.generation_id != generation_id
                or run.tool_id != tool_id
                or run.state != "succeeded"
                or run.parent_run_id is not None
                or run.cancel_requested_at
                or generation.cancelled_at
                or (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                )
            ):
                raise ToolError("TOOL_FORBIDDEN")
            return await self._research_output(session, run, definition)

    async def research_snapshot(
        self,
        session: AsyncSession,
        owner: UUID,
        conversation: UUID,
        generation: UUID,
        run_id: UUID,
        tool_id: str,
    ) -> SearchResult | SourceDocument:
        """Read immutable evidence without granting permission to execute again.

        The enclosing reader checks the generation and non-deleted conversation.
        Historical reads survive flag/policy changes and cancellation; every run,
        input, result schema and digest is still bound to that exact scope.
        """
        run = await session.scalar(
            select(ToolRun).where(
                ToolRun.id == run_id,
                ToolRun.owner_id == owner,
                ToolRun.conversation_id == conversation,
                ToolRun.generation_id == generation,
                ToolRun.tool_id == tool_id,
                ToolRun.state == "succeeded",
                ToolRun.parent_run_id.is_(None),
                ToolRun.cancel_requested_at.is_(None),
            )
        )
        if run is None:
            raise ToolError("TOOL_FORBIDDEN")
        definition = self._registry.get(tool_id)
        if run.schema_version != definition.schema_version:
            raise ToolError("TOOL_OUTPUT_INVALID")
        return await self._research_output(session, run, definition)

    async def _research_output(
        self,
        session: AsyncSession,
        run: ToolRun,
        definition: RegisteredTool,
    ) -> SearchResult | SourceDocument:
        value = definition.validate_input(
            encode_payload(run.input), cast(InvocationKind, run.invocation_kind)
        )
        if payload_digest(canonical_payload(value)) != run.input_digest:
            raise ToolError("TOOL_OUTPUT_INVALID")
        result = await session.get(ToolResult, (run.id, 1))
        if result is None or result.output_schema != definition.name:
            raise ToolError("TOOL_OUTPUT_INVALID")
        output = definition.validate_output(encode_payload(result.output))
        if payload_digest(canonical_payload(output)) != result.result_digest:
            raise ToolError("TOOL_OUTPUT_INVALID")
        if isinstance(output, SearchResult):
            if (
                output.provider != run.provider_key
                or output.config_version != run.config_version
                or output.provider != "searxng"
                or len({s.source_id for s in output.sources}) != len(output.sources)
                or any(
                    s.source_id != search_source_id(output.config_version, str(s.url))
                    for s in output.sources
                )
            ):
                raise ToolError("TOOL_OUTPUT_INVALID")
            return output
        if isinstance(output, SourceDocument):
            source = await self._search_source(session, run, output.source_id)
            value = definition.validate_input(encode_payload(run.input), "research_step")
            if (
                not isinstance(value, FetchInput)
                or value.source_id != source.source_id
                or hashlib.sha256(output.text.encode("utf-8")).hexdigest() != output.digest
            ):
                raise ToolError("TOOL_OUTPUT_INVALID")
            return output
        raise ToolError("TOOL_OUTPUT_INVALID")

    async def _search_source(
        self, session: AsyncSession, fetch: ToolRun, source_id: UUID
    ) -> SearchSource:
        # Never look up a UUID globally. The trusted caller explicitly selects a
        # search run; all four scope dimensions are checked before reading its data.
        if fetch.tool_id != "web.fetch.v1" or fetch.source_search_run_id is None:
            raise ToolError("TOOL_FORBIDDEN")
        search = await session.scalar(
            select(ToolRun).where(
                ToolRun.id == fetch.source_search_run_id,
                ToolRun.owner_id == fetch.owner_id,
                ToolRun.conversation_id == fetch.conversation_id,
                ToolRun.generation_id == fetch.generation_id,
                ToolRun.parent_run_id == fetch.parent_run_id,
                ToolRun.tool_id == "web.search.v1",
                ToolRun.state == "succeeded",
                ToolRun.cancel_requested_at.is_(None),
            )
        )
        if search is None:
            raise ToolError("TOOL_FORBIDDEN")
        results = list(
            await session.scalars(select(ToolResult).where(ToolResult.run_id == search.id).limit(2))
        )
        if len(results) != 1:
            raise ToolError("TOOL_FORBIDDEN")
        saved = results[0]
        try:
            definition = self._registry.get("web.search.v1")
            value = definition.validate_output(encode_payload(saved.output))
            if (
                not isinstance(value, SearchResult)
                or saved.result_version != 1
                or saved.output_schema != definition.name
                or search.schema_version != definition.schema_version
                or value.provider != search.provider_key
                or value.provider != "searxng"
                or value.config_version != search.config_version
                or payload_digest(canonical_payload(value)) != saved.result_digest
                or len({s.source_id for s in value.sources}) != len(value.sources)
                or any(
                    s.source_id != search_source_id(value.config_version, str(s.url))
                    for s in value.sources
                )
            ):
                raise ToolError("TOOL_FORBIDDEN")
        except ToolError, ValueError, TypeError:
            raise ToolError("TOOL_FORBIDDEN") from None
        matches = [s for s in value.sources if s.source_id == source_id]
        if len(matches) != 1:
            raise ToolError("TOOL_FORBIDDEN")
        return matches[0]

    async def resolve_source(self, context: GenerationToolContext, source_id: UUID) -> SearchSource:
        context.check()
        async with self._database() as session:
            fetch, generation = await self._run(
                session, context.owner_id, context.run_id, write=False
            )
            conversation = await session.get(ChatConversation, context.conversation_id)
            if (
                fetch.conversation_id != context.conversation_id
                or fetch.generation_id != context.generation_id
                or fetch.parent_run_id != context.parent_run_id
                or fetch.source_search_run_id != context.source_search_run_id
                or fetch.provider_key != context.provider_key
                or fetch.config_version != context.config_version
                or fetch.reservation_id != context.reservation_id
                or fetch.state != "running"
                or fetch.cancel_requested_at is not None
                or (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                )
                or conversation is None
                or conversation.archived_at is not None
                or payload_digest(encode_payload(fetch.input)) != fetch.input_digest
            ):
                raise ToolError("TOOL_FORBIDDEN")
            value = self._registry.get("web.fetch.v1").validate_input(
                encode_payload(fetch.input), cast(InvocationKind, fetch.invocation_kind)
            )
            if not isinstance(value, FetchInput) or value.source_id != source_id:
                raise ToolError("TOOL_FORBIDDEN")
            await self._live_parent(session, fetch)
            source = await self._search_source(session, fetch, source_id)
        context.check()
        return source

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
                if (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                ) or run.cancel_requested_at:
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
            # awaiting_approval is public only with the authoritative grant.
            await self._event(
                session, generation, run, "tool.progress" if target == "awaiting_approval" else None
            )
            return run

    async def complete(
        self,
        owner_id: UUID,
        run_id: UUID,
        payload: bytes,
        *,
        execution_id: UUID | None = None,
        policy: ToolPolicy | None = None,
    ) -> ToolResult:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner_id)
            run, generation = await self._run(session, owner_id, run_id, write=True)
            if run.execution_id != execution_id:
                raise ToolError("TOOL_STATE_CONFLICT")
            definition = self._registry.get(run.tool_id)
            if policy is not None:
                permission = policy.require(definition, run)
                if run.policy_snapshot != permission.snapshot(definition.permission):
                    raise ToolError("TOOL_FORBIDDEN")
            value = definition.validate_output(payload)
            if isinstance(value, SourceDocument):
                if value.digest != payload_digest(value.text.encode("utf-8")):
                    raise ToolError("TOOL_OUTPUT_INVALID")
                fetch_input = definition.validate_input(
                    encode_payload(run.input), cast(InvocationKind, run.invocation_kind)
                )
                if (
                    not isinstance(fetch_input, FetchInput)
                    or value.source_id != fetch_input.source_id
                ):
                    raise ToolError("TOOL_OUTPUT_INVALID")
                await self._search_source(session, run, value.source_id)
            digest = payload_digest(canonical_payload(value))
            if run.state == "succeeded":
                result = await session.get(ToolResult, (run_id, 1))
                if result is not None and result.result_digest == digest:
                    return result
                raise ToolError("TOOL_CONFLICT")
            check_transition(cast(ToolRunState, run.state), "succeeded")
            if (
                generation.status not in ("queued", "running")
                or generation.cancelled_at is not None
            ) or run.cancel_requested_at:
                raise ToolError("TOOL_STATE_CONFLICT")
            await self._live_parent(session, run)
            if min(run.deadline_at, run.execution_deadline_at or run.deadline_at) <= utc_now():
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
            if run.reservation_id is not None:
                reservation = await session.scalar(
                    select(BudgetReservation).where(BudgetReservation.id == run.reservation_id)
                )
                if reservation is None:
                    raise ToolError("TOOL_STATE_CONFLICT")
                await BudgetCoordinator(self._database).settle_in(
                    session, reservation, unused=False
                )
            await session.flush()
            await self._event(session, generation, run, "tool.result")
            await self._event(session, generation, run)
            return result

    async def claim(self, owner: UUID, run_id: UUID, policy: ToolPolicy) -> ToolRun:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            run, generation = await self._run(session, owner, run_id, write=True)
            definition = self._registry.get(run.tool_id)
            permission = policy.require(definition, run)
            if run.state not in ("queued", "awaiting_approval"):
                raise ToolError("TOOL_STATE_CONFLICT")
            if run.cancel_requested_at or (
                generation.status not in ("queued", "running")
                or generation.cancelled_at is not None
            ):
                raise ToolError("TOOL_CANCELLED")
            if run.deadline_at <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            parent_deadline = await self._live_parent(session, run)
            if permission.decision == "approval_required":
                approval = await session.scalar(
                    select(ToolApproval).where(ToolApproval.run_id == run.id).with_for_update()
                )
                if approval is None or approval.state == "pending":
                    raise ToolError("APPROVAL_REQUIRED")
                if approval.expires_at <= utc_now() or approval.state == "expired":
                    raise ToolError("APPROVAL_EXPIRED")
                if (
                    approval.state != "approved"
                    or approval.owner_id != owner
                    or approval.input_digest != run.input_digest
                    or approval.provider_key != permission.provider_key
                    or approval.config_version != permission.config_version
                    or approval.permission_scope != definition.permission
                    or approval.max_calls < 1
                    or approval.max_cost < permission.per_call.cost
                    or approval.currency != permission.currency
                ):
                    raise ToolError("TOOL_FORBIDDEN")
                run.approval_id = approval.id
            prior = list(
                await session.scalars(
                    select(BudgetReservation)
                    .join(ToolRun, ToolRun.id == BudgetReservation.run_id)
                    .where(
                        ToolRun.owner_id == owner,
                        ToolRun.generation_id == run.generation_id,
                        BudgetReservation.state != "released",
                    )
                )
            )
            if any(r.currency != permission.currency for r in prior):
                raise ToolError("BUDGET_LIMIT")
            total = BudgetAmount(
                **{
                    k: sum(getattr(r, k) for r in prior) + getattr(permission.per_call, k)
                    for k in DIMENSIONS
                }
            )
            if not total.fits(permission.generation_limit):
                raise ToolError("BUDGET_LIMIT")
            reservation = await BudgetCoordinator(self._database).reserve_in(
                session,
                owner,
                "tools",
                str(run.id),
                1,
                run.input_digest,
                permission.per_call,
                permission.daily_limit,
                permission.currency,
                run_id=run.id,
            )
            if reservation.state != "reserved":
                raise ToolError("TOOL_STATE_CONFLICT")
            run.reservation_id = reservation.id
            run.execution_id = uuid4()
            run.execution_deadline_at = min(
                run.deadline_at,
                utc_now() + timedelta(seconds=definition.timeout_policy.total_seconds),
                parent_deadline or run.deadline_at,
            )
            run.policy_snapshot = permission.snapshot(definition.permission)
            run.state, run.started_at = "running", utc_now()
            await session.flush()
            await self._event(session, generation, run)
            return run

    async def dispatch(
        self,
        owner: UUID,
        run_id: UUID,
        execution_id: UUID,
        policy: ToolPolicy,
        *,
        retry: bool = False,
    ) -> ToolRun:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            run, generation = await self._run(session, owner, run_id, write=True)
            definition = self._registry.get(run.tool_id)
            permission = policy.require(definition, run)
            if run.state != "running" or run.execution_id != execution_id:
                raise ToolError("TOOL_STATE_CONFLICT")
            if run.policy_snapshot != permission.snapshot(definition.permission):
                raise ToolError("TOOL_FORBIDDEN")
            if run.cancel_requested_at or (
                generation.status not in ("queued", "running")
                or generation.cancelled_at is not None
            ):
                raise ToolError("TOOL_CANCELLED")
            if min(run.deadline_at, run.execution_deadline_at or run.deadline_at) <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            await self._live_parent(session, run)
            if permission.decision == "approval_required":
                approval = await session.scalar(
                    select(ToolApproval).where(ToolApproval.run_id == run.id)
                )
                calls = 2 if retry else 1
                if approval is None or approval.expires_at <= utc_now():
                    raise ToolError("APPROVAL_EXPIRED")
                if (
                    approval.state != "approved"
                    or approval.owner_id != owner
                    or approval.input_digest != run.input_digest
                    or approval.provider_key != permission.provider_key
                    or approval.config_version != permission.config_version
                    or approval.permission_scope != definition.permission
                    or approval.currency != permission.currency
                    or approval.max_calls < calls
                    or approval.max_cost < permission.per_call.cost * calls
                ):
                    raise ToolError("TOOL_FORBIDDEN")
            reservation = await session.scalar(
                select(BudgetReservation).where(BudgetReservation.id == run.reservation_id)
            )
            if reservation is None:
                raise ToolError("TOOL_STATE_CONFLICT")
            if retry:
                if (
                    run.attempt != 1
                    or definition.retry_policy.max_retries != 1
                    or not definition.retry_policy.idempotent
                ):
                    raise ToolError("TOOL_FORBIDDEN")
                prior = list(
                    await session.scalars(
                        select(BudgetReservation)
                        .join(ToolRun, ToolRun.id == BudgetReservation.run_id)
                        .where(
                            ToolRun.owner_id == owner,
                            ToolRun.generation_id == run.generation_id,
                            BudgetReservation.state != "released",
                        )
                    )
                )
                total = BudgetAmount(
                    **{
                        k: sum(getattr(r, k) for r in prior) + getattr(permission.per_call, k)
                        for k in DIMENSIONS
                    }
                )
                if not total.fits(permission.generation_limit):
                    raise ToolError("BUDGET_LIMIT")
                await BudgetCoordinator(self._database).settle_in(
                    session, reservation, unused=False
                )
                reservation = await BudgetCoordinator(self._database).reserve_in(
                    session,
                    owner,
                    "tools",
                    str(run.id),
                    2,
                    run.input_digest,
                    permission.per_call,
                    permission.daily_limit,
                    permission.currency,
                    run_id=run.id,
                )
                run.attempt = 2
                run.reservation_id = reservation.id
            elif reservation.state != "reserved":
                raise ToolError("TOOL_STATE_CONFLICT")
            # Mark before network: crash here is conservatively a dispatched call.
            reservation.state = "dispatched"
            run.dispatched_at = utc_now()
            await session.flush()
            return run

    async def approval_required(
        self, owner: UUID, run_id: UUID, policy: ToolPolicy
    ) -> ToolApproval:
        async with self._database() as session, session.begin():
            run, generation = await self._run(session, owner, run_id, write=True)
            definition = self._registry.get(run.tool_id)
            permission = policy.require(definition, run)
            if (
                permission.decision != "approval_required"
                or run.state not in ("queued", "awaiting_approval")
                or (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                )
                or run.cancel_requested_at
            ):
                raise ToolError("TOOL_STATE_CONFLICT")
            if run.deadline_at <= utc_now():
                raise ToolError("TOOL_TIMEOUT")
            await self._live_parent(session, run)
            existing = await session.scalar(
                select(ToolApproval).where(ToolApproval.run_id == run_id)
            )
            if existing is not None:
                return existing
            approval = ToolApproval(
                owner_id=owner,
                run_id=run_id,
                input_digest=run.input_digest,
                provider_key=permission.provider_key,
                config_version=permission.config_version,
                permission_scope=definition.permission,
                max_calls=1 + definition.retry_policy.max_retries,
                max_cost=permission.per_call.cost * (1 + definition.retry_policy.max_retries),
                currency=permission.currency,
                expires_at=min(run.deadline_at, utc_now() + timedelta(minutes=5)),
            )
            run.state = "awaiting_approval"
            session.add(approval)
            await session.flush()
            await self._event(session, generation, run)
            return approval

    async def decide(
        self,
        owner: UUID,
        approval_id: UUID,
        request_id: UUID,
        digest: str,
        decision: str,
        *,
        policy: ToolPolicy,
    ) -> ToolApproval:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            approval = await session.get(ToolApproval, approval_id)
            if approval is None or approval.owner_id != owner:
                raise ToolError("TOOL_NOT_FOUND")
            run, generation = await self._run(session, owner, approval.run_id, write=True)
            policy.require(self._registry.get(run.tool_id), run)
            approval = await session.scalar(
                select(ToolApproval)
                .where(ToolApproval.id == approval_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if approval is None:
                raise ToolError("TOOL_NOT_FOUND")
            if approval.input_digest != digest:
                raise ToolError("TOOL_CONFLICT")
            target = "approved" if decision == "approve" else "denied"
            if decision not in ("approve", "deny"):
                raise ToolError("TOOL_INPUT_INVALID")
            if approval.state != "pending":
                if approval.decision_request_id == request_id and approval.state == target:
                    return approval
                raise ToolError(
                    "APPROVAL_EXPIRED" if approval.state == "expired" else "TOOL_CONFLICT"
                )
            duplicate = await session.scalar(
                select(ToolApproval).where(ToolApproval.decision_request_id == request_id)
            )
            if duplicate is not None:
                raise ToolError("TOOL_CONFLICT")
            if (
                run.state != "awaiting_approval"
                or run.cancel_requested_at
                or (
                    generation.status not in ("queued", "running")
                    or generation.cancelled_at is not None
                )
            ):
                raise ToolError("TOOL_STATE_CONFLICT")
            if approval.expires_at <= utc_now() or run.deadline_at <= utc_now():
                raise ToolError("APPROVAL_EXPIRED")
            approval.state, approval.decided_at, approval.decision_request_id = (
                target,
                utc_now(),
                request_id,
            )
            if target == "denied":
                run.state, run.finished_at, run.error_code = "failed", utc_now(), "TOOL_FORBIDDEN"
            await session.flush()
            await self._event(
                session, generation, run, "tool.progress" if target == "approved" else None
            )
            return approval

    @staticmethod
    def _approval_response(approval: ToolApproval) -> ToolApprovalResponse:
        return ToolApprovalResponse(
            id=approval.id,
            runId=approval.run_id,
            inputDigest=approval.input_digest,
            permissionScope=approval.permission_scope,
            provider=approval.provider_key,
            configVersion=approval.config_version,
            maxCalls=approval.max_calls,
            maxCost=str(approval.max_cost),
            currency=approval.currency,
            state=cast(ApprovalState, approval.state),
            expiresAt=approval.expires_at,
            decidedAt=approval.decided_at,
        )

    async def public_approval(self, owner: UUID, approval_id: UUID) -> ToolApprovalResponse:
        async with self._database() as session:
            approval = await session.get(ToolApproval, approval_id)
            if approval is None or approval.owner_id != owner:
                raise ToolError("TOOL_NOT_FOUND")
            await self._run(session, owner, approval.run_id, write=False)
            return self._approval_response(approval)

    async def public_snapshot(self, owner: UUID, run_id: UUID) -> ToolRunResponse:
        async with self._database() as session, session.begin():
            # Scope lock makes run/result/approval a consistent projection.
            run, _ = await self._run(session, owner, run_id, write=False)
            await session.execute(
                select(ChatGeneration.id)
                .where(ChatGeneration.id == run.generation_id)
                .with_for_update()
            )
            run, _ = await self._run(session, owner, run_id, write=False)
            await session.refresh(run)
            result = await session.get(ToolResult, (run_id, 1))
            output: SearchResult | SourceDocument | None = None
            if result is not None:
                value = self._registry.get(run.tool_id).validate_output(
                    encode_payload(result.output)
                )
                if isinstance(value, (SearchResult, SourceDocument)):
                    output = value
            approval = await session.scalar(
                select(ToolApproval).where(ToolApproval.run_id == run.id)
            )
            snapshot = ToolRunSnapshot(
                **{name: getattr(run, name) for name in ToolRunSnapshot.model_fields}
            )
            return ToolRunResponse(
                run=snapshot,
                latestResult=output,
                errorCode=cast(ToolErrorCode | None, run.error_code),
                approval=self._approval_response(approval) if approval is not None else None,
            )

    async def finalize(
        self,
        owner: UUID,
        run_id: UUID,
        state: ToolRunState,
        code: ToolErrorCode,
        *,
        execution_id: UUID | None = None,
        recovery: bool = False,
    ) -> None:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            run, generation = await self._run(session, owner, run_id, write=True, finalizing=True)
            if run.state in TERMINAL_STATES or (not recovery and run.execution_id != execution_id):
                return
            check_transition(cast(ToolRunState, run.state), state)
            run.state, run.error_code, run.finished_at = state, code, utc_now()
            approvals = await session.scalars(
                select(ToolApproval).where(
                    ToolApproval.run_id == run.id, ToolApproval.state.in_(("pending", "approved"))
                )
            )
            for approval in approvals:
                approval.state, approval.decided_at = "expired", utc_now()
            if run.reservation_id is not None:
                reservation = await session.scalar(
                    select(BudgetReservation).where(BudgetReservation.id == run.reservation_id)
                )
                if reservation is not None:
                    await BudgetCoordinator(self._database).settle_in(
                        session, reservation, unused=True, unknown=state == "outcome_unknown"
                    )
            await self._event(session, generation, run)

    async def cancel_runs(
        self, owner: UUID, generation_id: UUID, *, root_id: UUID | None = None
    ) -> set[UUID]:
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            runs = list(
                await session.scalars(
                    select(ToolRun)
                    .where(ToolRun.owner_id == owner, ToolRun.generation_id == generation_id)
                    .order_by(ToolRun.created_at)
                )
            )
            selected = {r.id for r in runs} if root_id is None else {root_id}
            while True:
                children = {r.id for r in runs if r.parent_run_id in selected}
                if children <= selected:
                    break
                selected |= children
            active: set[UUID] = set()
            for candidate in runs:
                if candidate.id not in selected:
                    continue
                run, generation = await self._run(
                    session, owner, candidate.id, write=True, finalizing=True
                )
                if run.state in TERMINAL_STATES:
                    continue
                active.add(run.id)
                if run.cancel_requested_at is not None:
                    continue
                run.cancel_requested_at = utc_now()
                # Commit cancellation fence first. The worker closes network then finalizes.
                if run.state != "running":
                    run.state, run.finished_at, run.error_code = (
                        "cancelled",
                        utc_now(),
                        "TOOL_CANCELLED",
                    )
                approvals = await session.scalars(
                    select(ToolApproval).where(
                        ToolApproval.run_id == run.id,
                        ToolApproval.state.in_(("pending", "approved")),
                    )
                )
                for approval in approvals:
                    approval.state, approval.decided_at = "expired", utc_now()
                await self._event(
                    session, generation, run, "tool.progress" if run.state == "running" else None
                )
            return active

    async def recover(self, owner: UUID) -> None:
        async with self._database() as session:
            rows = list(
                await session.scalars(
                    select(ToolRun).where(
                        ToolRun.owner_id == owner, ToolRun.state.not_in(TERMINAL_STATES)
                    )
                )
            )
        for run in rows:
            try:
                definition = self._registry.get(run.tool_id)
                unknown = run.dispatched_at is not None and not definition.retry_policy.idempotent
            except ToolError:
                unknown = run.dispatched_at is not None
            await self.finalize(
                owner,
                run.id,
                "outcome_unknown"
                if unknown
                else "cancelled"
                if run.cancel_requested_at
                else "interrupted",
                "PROVIDER_OUTCOME_UNKNOWN"
                if unknown
                else "TOOL_CANCELLED"
                if run.cancel_requested_at
                else "TOOL_INTERRUPTED",
                recovery=True,
            )
        async with self._database() as session, session.begin():
            approvals = await session.scalars(
                select(ToolApproval).where(
                    ToolApproval.owner_id == owner, ToolApproval.state.in_(("pending", "approved"))
                )
            )
            for approval in approvals:
                approval.state, approval.decided_at = "expired", utc_now()

    async def expire_pending(self, owner: UUID) -> None:
        async with self._database() as session:
            rows = list(
                await session.scalars(
                    select(ToolRun).where(
                        ToolRun.owner_id == owner,
                        ToolRun.state.in_(("queued", "awaiting_approval")),
                        ToolRun.deadline_at <= utc_now(),
                    )
                )
            )
        for run in rows:
            await self.finalize(owner, run.id, "timed_out", "TOOL_TIMEOUT")
        async with self._database() as session:
            expired = list(
                await session.scalars(
                    select(ToolRun)
                    .join(ToolApproval, ToolApproval.run_id == ToolRun.id)
                    .where(
                        ToolRun.owner_id == owner,
                        ToolRun.state == "awaiting_approval",
                        ToolApproval.expires_at <= utc_now(),
                    )
                )
            )
        for run in expired:
            await self.finalize(owner, run.id, "failed", "APPROVAL_EXPIRED")
        async with self._database() as session, session.begin():
            await lock_owner(session, owner)
            approvals = list(
                await session.scalars(
                    select(ToolApproval).where(
                        ToolApproval.owner_id == owner,
                        ToolApproval.state.in_(("pending", "approved")),
                        ToolApproval.expires_at <= utc_now(),
                    )
                )
            )
            for approval in approvals:
                approval.state, approval.decided_at = "expired", utc_now()
