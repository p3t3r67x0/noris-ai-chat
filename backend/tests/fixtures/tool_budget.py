"""App-only text ledger double for existing DB-free HTTP/unit tests."""

from uuid import UUID

from noris_ai.chat.repository import ModelDatabase
from noris_ai.tools.budget import BudgetCoordinator
from noris_ai.tools.errors import ToolError


class MemoryTextBudget(BudgetCoordinator):
    def __init__(self, database: ModelDatabase) -> None:
        super().__init__(database)
        self.phases: dict[tuple[UUID, str], str] = {}

    async def reserve_text(
        self, owner: UUID, phase: str, digest: str, tokens: int, limit: int
    ) -> None:
        if tokens > limit:
            raise ToolError("BUDGET_LIMIT")
        self.phases[(owner, phase)] = "reserved"

    async def dispatch_text(self, owner: UUID, phase: str) -> None:
        self.phases[(owner, phase)] = "dispatched"

    async def finish_text(self, owner: UUID, phase: str, *, unknown: bool = False) -> None:
        self.phases[(owner, phase)] = "unknown" if unknown else "accounted"

    async def recover_text(self, owner: UUID) -> None:
        return
