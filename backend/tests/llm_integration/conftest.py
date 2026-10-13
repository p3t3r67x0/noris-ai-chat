import pytest

from tests.fixtures.tool_budget import MemoryTextBudget


@pytest.fixture(autouse=True)
def db_free_app_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # These local HTTP simulators do not require PostgreSQL.
    monkeypatch.setattr("noris_ai.main.BudgetCoordinator", MemoryTextBudget)
