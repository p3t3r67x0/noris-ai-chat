import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


@pytest.fixture
def migration_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    url = os.environ.get("NORIS_TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "Set NORIS_TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test"
        )
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        pytest.fail("Integration tests require a disposable database with a name ending in _test")
    monkeypatch.setenv("NORIS_DATABASE_URL", url)
    monkeypatch.setenv("NORIS_MIGRATION_DATABASE_URL", url)
    monkeypatch.setenv("NORIS_ENVIRONMENT", "test")
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.downgrade(config, "base")
    try:
        yield config
    finally:
        command.downgrade(config, "base")
