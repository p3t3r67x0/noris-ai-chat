"""Only trusted server orchestration calls execute; no model or HTTP name dispatch."""

import asyncio
import json
import random
from datetime import timedelta
from typing import cast
from uuid import UUID

import anyio
from sqlalchemy.exc import SQLAlchemyError

from noris_ai.chat.repository import utc_now
from noris_ai.tools.cancellation import CancelHandle, GenerationToolContext
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolResult, ToolRun
from noris_ai.tools.policy import ToolPolicy
from noris_ai.tools.registry import RegisteredTool, ToolRegistry, canonical_payload
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.schemas import (
    TERMINAL_STATES,
    InvocationKind,
    ToolRunCreate,
    ToolRunState,
    ToolSchema,
)


async def invoke(
    definition: RegisteredTool, context: GenerationToolContext, value: ToolSchema
) -> ToolSchema:
    if definition.handler is None:
        raise ToolError("TOOL_UNAVAILABLE")
    return await definition.handler(context, value)


class ToolRuntime:
    def __init__(
        self, repository: ToolRepository, registry: ToolRegistry, policy: ToolPolicy
    ) -> None:
        self.repository, self.registry, self.policy = repository, registry, policy
        self._active: dict[tuple[UUID, UUID], asyncio.Task[ToolResult]] = {}
        self._cancels: dict[UUID, asyncio.Event] = {}
        self._closing = False

    async def execute(self, owner: UUID, request: ToolRunCreate, payload: bytes) -> ToolResult:
        if self._closing:
            raise ToolError("TOOL_INTERRUPTED")
        self.policy.require(self.registry.get(request.tool_id))
        try:
            run, _ = await self.repository.create_run(owner, request, payload)
        except SQLAlchemyError:
            raise ToolError("TOOL_UNAVAILABLE") from None
        if run.state == "succeeded":
            result = await self.repository.get_result(owner, run.id)
            if result is None:
                raise ToolError("TOOL_STATE_CONFLICT")
            return result
        if run.state in TERMINAL_STATES:
            raise ToolError("TOOL_STATE_CONFLICT")
        key = (owner, run.id)
        task = self._active.get(key)
        if task is None:
            task = asyncio.create_task(self._execute(owner, run))
            self._active[key] = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                await self.cancel(owner, run.generation_id, root_id=run.id)
                await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            if task.done() and self._active.get(key) is task:
                self._active.pop(key, None)

    async def _execute(self, owner: UUID, original: ToolRun) -> ToolResult:
        definition = self.registry.get(original.tool_id)
        run = original
        cancel = asyncio.Event()
        self._cancels[run.id] = cancel
        handler_task: asyncio.Task[ToolSchema] | None = None
        watcher: asyncio.Task[None] | None = None
        claimed_execution_id: UUID | None = None
        try:
            if self._closing:
                raise ToolError("TOOL_INTERRUPTED")
            try:
                run = await self.repository.claim(owner, run.id, self.policy)
            except ToolError as error:
                if error.code == "APPROVAL_REQUIRED":
                    await self.repository.approval_required(owner, run.id, self.policy)
                raise
            if run.execution_id is None:
                raise ToolError("TOOL_STATE_CONFLICT")
            execution_id = run.execution_id
            claimed_execution_id = execution_id
            deadline = run.execution_deadline_at or run.deadline_at
            value = definition.validate_input(
                json.dumps(run.input).encode(), cast(InvocationKind, run.invocation_kind)
            )

            async def watch() -> None:
                while True:
                    try:
                        current = await self.repository.get_run(owner, run.id)
                        if current.cancel_requested_at or current.state in TERMINAL_STATES:
                            cancel.set()
                            return
                        # Use the same authoritative generation/parent checks as dispatch.
                        await self.repository.check_live(owner, run.id)
                    except ToolError:
                        cancel.set()
                        return
                    await asyncio.sleep(0.1)

            watcher = asyncio.create_task(watch())
            for attempt in range(1 + definition.retry_policy.max_retries):
                if cancel.is_set():
                    raise ToolError("TOOL_CANCELLED")
                run = await self.repository.dispatch(
                    owner, run.id, execution_id, self.policy, retry=attempt > 0
                )
                if (
                    run.reservation_id is None
                    or run.provider_key is None
                    or run.config_version is None
                ):
                    raise ToolError("TOOL_STATE_CONFLICT")
                context = GenerationToolContext(
                    owner,
                    run.conversation_id,
                    run.generation_id,
                    run.id,
                    run.parent_run_id,
                    run.reservation_id,
                    run.approval_id,
                    run.provider_key,
                    run.config_version,
                    deadline,
                    CancelHandle(cancel),
                    definition.permission,
                    self.policy.require(definition, run).per_call,
                )
                context.check()
                handler = definition.handler
                if handler is None:
                    raise ToolError("TOOL_UNAVAILABLE")

                handler_task = asyncio.create_task(invoke(definition, context, value))
                cancelled = asyncio.create_task(cancel.wait())
                try:
                    async with asyncio.timeout(max(0, (deadline - utc_now()).total_seconds())):
                        done, _ = await asyncio.wait(
                            (handler_task, cancelled, watcher), return_when=asyncio.FIRST_COMPLETED
                        )
                        if watcher in done:
                            await watcher  # DB errors stop dispatch; never ignore a broken fence.
                        if cancel.is_set():
                            raise ToolError("TOOL_CANCELLED")
                        result = await handler_task
                    context.check()
                    return await self.repository.complete(
                        owner,
                        run.id,
                        canonical_payload(result),
                        execution_id=run.execution_id,
                        policy=self.policy,
                    )
                except ToolError as error:
                    if not (
                        attempt == 0
                        and definition.retry_policy.max_retries == 1
                        and error.code in ("PROVIDER_RATE_LIMIT", "PROVIDER_ERROR")
                    ):
                        raise
                    # One bounded jitter; retry must obtain a fresh persisted reservation.
                    delay = random.uniform(0.05, 0.2)  # noqa: S311 - scheduling jitter
                    if utc_now() + timedelta(seconds=delay) >= deadline:
                        raise ToolError("TOOL_TIMEOUT") from None
                    await asyncio.sleep(delay)
                finally:
                    cancelled.cancel()
                    handler_task.cancel()
                    await asyncio.gather(cancelled, handler_task, return_exceptions=True)
            raise ToolError("PROVIDER_ERROR")
        except (asyncio.CancelledError, Exception) as cause:
            error = (
                cause
                if isinstance(cause, ToolError)
                else ToolError(
                    "TOOL_TIMEOUT"
                    if isinstance(cause, TimeoutError)
                    else "TOOL_UNAVAILABLE"
                    if isinstance(cause, SQLAlchemyError)
                    else "TOOL_INTERRUPTED"
                    if isinstance(cause, asyncio.CancelledError)
                    else "PROVIDER_ERROR"
                )
            )
            if error.code == "APPROVAL_REQUIRED":
                raise error from None
            if error.code == "TOOL_STATE_CONFLICT" and claimed_execution_id is not None:
                try:
                    await self.repository.check_live(owner, run.id)
                except ToolError as stopped:
                    error = ToolError(
                        "TOOL_TIMEOUT" if stopped.code == "TOOL_TIMEOUT" else "TOOL_CANCELLED"
                    )
                except SQLAlchemyError:
                    error = ToolError("TOOL_UNAVAILABLE")
            if error.code == "TOOL_CANCELLED" and self._closing:
                error = ToolError("TOOL_INTERRUPTED")
            states: dict[str, ToolRunState] = {
                "TOOL_CANCELLED": "cancelled",
                "TOOL_INTERRUPTED": "interrupted",
                "TOOL_TIMEOUT": "timed_out",
            }
            state = states.get(error.code, "failed")
            if (
                run.dispatched_at is not None
                and not definition.retry_policy.idempotent
                and error.code != "PROVIDER_RATE_LIMIT"
            ):
                state, error = "outcome_unknown", ToolError("PROVIDER_OUTCOME_UNKNOWN")
            # An unclaimed concurrent worker must never finalize someone else's claim.
            if claimed_execution_id is not None or original.state != "running":
                with anyio.CancelScope(shield=True):
                    try:
                        await self.repository.finalize(
                            owner, run.id, state, error.code, execution_id=claimed_execution_id
                        )
                    except SQLAlchemyError:
                        # Keep the durable reservation/fence for recovery. No raw
                        # database or provider exception leaves the dispatcher.
                        raise ToolError("TOOL_UNAVAILABLE") from None
            raise error from None
        finally:
            if watcher is not None:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            self._cancels.pop(run.id, None)

    async def cancel(self, owner: UUID, generation: UUID, *, root_id: UUID | None = None) -> None:
        ids = await self.repository.cancel_runs(owner, generation, root_id=root_id)
        for run_id in ids:
            event = self._cancels.get(run_id)
            if event is not None:
                event.set()

    async def close(self) -> None:
        self._closing = True
        for event in self._cancels.values():
            event.set()
        await asyncio.gather(*self._active.values(), return_exceptions=True)
        self._active.clear()
