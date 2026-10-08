import asyncio

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from noris_ai.core.config import Settings
from noris_ai.main import create_app

pytestmark = pytest.mark.integration


def health_status(path: str) -> int:
    async def run() -> int:
        app = create_app()
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            return (await client.get(path)).status_code

    return asyncio.run(run())


def test_baseline_upgrade_repeat_downgrade_and_upgrade(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")
    command.upgrade(migration_config, "head")
    command.check(migration_config)
    assert health_status("/api/v1/health/ready") == 200
    command.downgrade(migration_config, "base")
    assert health_status("/api/v1/health/ready") == 503
    assert health_status("/api/v1/health/live") == 200
    command.upgrade(migration_config, "head")
    assert health_status("/api/v1/health/ready") == 200


def test_database_transaction_rolls_back(migration_config: Config) -> None:
    async def run() -> None:
        engine = create_async_engine(Settings().database_url.get_secret_value())
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.execute(
                    text("CREATE TABLE foundation_rollback_probe (id integer)")
                )
                await transaction.rollback()
                result = await connection.execute(
                    text("SELECT to_regclass('foundation_rollback_probe')")
                )
                assert result.scalar_one() is None
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_unexpected_migration_revision_fails_readiness(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")

    async def modify_revision(value: str) -> None:
        engine = create_async_engine(Settings().database_url.get_secret_value())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE alembic_version SET version_num = :value"), {"value": value}
                )
        finally:
            await engine.dispose()

    asyncio.run(modify_revision("unexpected_revision"))
    try:
        assert health_status("/api/v1/health/ready") == 503
    finally:
        asyncio.run(modify_revision("0001_foundation"))
