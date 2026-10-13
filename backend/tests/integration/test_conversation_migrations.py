"""Both published sidebar migration branches converge without losing data."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from noris_ai.db.readiness import LATEST_REVISION

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "revision",
    [
        "0011_tool_foundation",
        "0012_conversation_visibility",
        "0012_conversation_pinning",
        "0013_conversation_pinning",
    ],
)
def test_sidebar_upgrade_and_rollback_preserve_published_schemas(
    migration_config: Config, revision: str
) -> None:
    command.upgrade(migration_config, revision)
    engine = create_engine(os.environ["NORIS_TEST_DATABASE_URL"])
    conversation, owner = uuid4(), uuid4()
    pinned_at = datetime(2026, 10, 12, 12, tzinfo=UTC)
    try:
        original_columns = {
            column["name"] for column in inspect(engine).get_columns("chat_conversation")
        }
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_conversation (id, owner_id, title, title_source, version) "
                    "VALUES (:id, :owner, 'Preserved conversation', 'manual', 7)"
                ),
                {"id": conversation, "owner": owner},
            )
            if "pinned_at" in original_columns:
                connection.execute(
                    text("UPDATE chat_conversation SET pinned_at = :pinned WHERE id = :id"),
                    {"id": conversation, "pinned": pinned_at},
                )
            if "sidebar_visible" in original_columns:
                connection.execute(
                    text("UPDATE chat_conversation SET sidebar_visible = false WHERE id = :id"),
                    {"id": conversation},
                )
            before = dict(
                connection.execute(text("SELECT * FROM chat_conversation")).one()._mapping
            )

        command.upgrade(migration_config, "head")
        command.upgrade(migration_config, "head")
        command.check(migration_config)
        with engine.connect() as connection:
            after = dict(connection.execute(text("SELECT * FROM chat_conversation")).one()._mapping)
            assert {column: after[column] for column in before} == before
            assert after["pinned_at"] == (pinned_at if "pinned_at" in original_columns else None)
            assert after["sidebar_visible"] is ("sidebar_visible" not in original_columns)
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all() == [LATEST_REVISION]
        assert "ix_chat_conversation_pinned_seek" in {
            index["name"] for index in inspect(engine).get_indexes("chat_conversation")
        }

        # A merge downgrade exposes both parents. Roll back only the newly
        # applied branch when restoring a database that originally had one.
        rollback_targets = {
            "0012_conversation_visibility": "0012_conversation_pinning@0011_tool_foundation",
            "0012_conversation_pinning": "0012_conversation_visibility@0011_tool_foundation",
        }
        command.downgrade(migration_config, rollback_targets.get(revision, revision))
        with engine.connect() as connection:
            assert (
                dict(connection.execute(text("SELECT * FROM chat_conversation")).one()._mapping)
                == before
            )
        assert {
            column["name"] for column in inspect(engine).get_columns("chat_conversation")
        } == original_columns
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    finally:
        engine.dispose()
