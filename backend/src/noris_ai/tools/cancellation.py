import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import anyio

from noris_ai.chat.repository import utc_now
from noris_ai.tools.budget import BudgetAmount
from noris_ai.tools.errors import ToolError


async def drain_cleanup(task: asyncio.Task[None]) -> None:
    """Existing cleanup fence shared by runtime and gateway; drain repeated cancels."""
    interrupted = False
    with anyio.CancelScope(shield=True):
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                interrupted = True
        task.result()
    if interrupted:
        raise asyncio.CancelledError


@dataclass(frozen=True)
class CancelHandle:
    event: asyncio.Event

    def check(self) -> None:
        if self.event.is_set():
            raise ToolError("TOOL_CANCELLED")


@dataclass(frozen=True)
class GenerationToolContext:
    owner_id: UUID
    conversation_id: UUID
    generation_id: UUID
    run_id: UUID
    parent_run_id: UUID | None
    reservation_id: UUID
    approval_id: UUID | None
    provider_key: str
    config_version: str
    deadline_at: datetime
    cancellation: CancelHandle
    permission_scope: str
    budget: BudgetAmount
    source_search_run_id: UUID | None = None

    def check(self) -> None:
        self.cancellation.check()
        if utc_now() >= self.deadline_at:
            raise ToolError("TOOL_TIMEOUT")
