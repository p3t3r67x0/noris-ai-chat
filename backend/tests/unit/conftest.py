import pytest

from tests.fixtures.tool_budget import MemoryTextBudget


@pytest.fixture(autouse=True)
def db_free_app_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only composition-root text accounting is doubled; real DB coverage is in integration.
    monkeypatch.setattr("noris_ai.main.BudgetCoordinator", MemoryTextBudget)
