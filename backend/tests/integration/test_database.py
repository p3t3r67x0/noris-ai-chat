import asyncio

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from noris_ai.core.config import Settings
from noris_ai.db.readiness import LATEST_REVISION
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
        asyncio.run(modify_revision(LATEST_REVISION))


def test_index_only_rollback_keeps_existing_chat_data(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")

    async def seed() -> None:
        engine = create_async_engine(Settings().database_url.get_secret_value())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("""
                    INSERT INTO chat_conversation (id,owner_id,title,title_source,version)
                    VALUES ('00000000-0000-0000-0000-000000000100',
                            '00000000-0000-0000-0000-000000000001','Keep me','manual',1)
                """)
                )
                await connection.execute(
                    text("""
                    INSERT INTO chat_message (id,conversation_id,role,content,status)
                    VALUES ('00000000-0000-0000-0000-000000000101',
                            '00000000-0000-0000-0000-000000000100','user','Keep text','completed')
                """)
                )
        finally:
            await engine.dispose()

    async def verify() -> None:
        engine = create_async_engine(Settings().database_url.get_secret_value())
        try:
            async with engine.connect() as connection:
                assert (
                    await connection.scalar(text("SELECT title FROM chat_conversation"))
                    == "Keep me"
                )
                assert (
                    await connection.scalar(text("SELECT content FROM chat_message")) == "Keep text"
                )
                assert (
                    await connection.scalar(
                        text(
                            "SELECT count(*) FROM pg_indexes "
                            "WHERE indexname='ix_chat_conversation_seek'"
                        )
                    )
                    == 0
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    command.downgrade(migration_config, "0004_chat_continuation")
    asyncio.run(verify())
    command.upgrade(migration_config, "head")
    command.check(migration_config)
