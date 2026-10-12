"""Learning upgrades preserve conversations from the current main schema."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration


def test_learning_migration_preserves_titles_claims_and_active_history(
    migration_config: Config,
) -> None:
    command.upgrade(migration_config, "0009_title_claim")
    conversation_id, owner_id, message_id = uuid4(), uuid4(), uuid4()
    engine = create_engine(os.environ["NORIS_TEST_DATABASE_URL"])
    existing = text(
        "SELECT title, title_source, title_generation_claimed_at, active_leaf_message_id, "
        "version FROM chat_conversation WHERE id = :id"
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_conversation "
                    "(id, owner_id, title, title_source, version, title_generation_claimed_at) "
                    "VALUES (:id, :owner, 'Synthetic preserved title', 'generated', 7, "
                    "'2026-10-12T10:00:00Z')"
                ),
                {"id": conversation_id, "owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO chat_message (id, conversation_id, role, content, status) "
                    "VALUES (:id, :conversation, 'user', "
                    "'Synthetic preserved history', 'completed')"
                ),
                {"id": message_id, "conversation": conversation_id},
            )
            connection.execute(
                text("UPDATE chat_conversation SET active_leaf_message_id = :leaf WHERE id = :id"),
                {"leaf": message_id, "id": conversation_id},
            )
            before = connection.execute(existing, {"id": conversation_id}).one()

        command.upgrade(migration_config, "head")
        with engine.connect() as connection:
            assert connection.execute(existing, {"id": conversation_id}).one() == before
            assert connection.execute(
                text(
                    "SELECT conversation_mode, reasoning_preference "
                    "FROM chat_conversation WHERE id = :id"
                ),
                {"id": conversation_id},
            ).one() == ("normal", None)
            assert (
                connection.execute(
                    text("SELECT content FROM chat_message WHERE id = :id"), {"id": message_id}
                ).scalar_one()
                == "Synthetic preserved history"
            )

        command.downgrade(migration_config, "0009_title_claim")
        with engine.connect() as connection:
            assert connection.execute(existing, {"id": conversation_id}).one() == before
        columns = {column["name"] for column in inspect(engine).get_columns("chat_conversation")}
        assert "title_generation_claimed_at" in columns
        assert "conversation_mode" not in columns
        assert "reasoning_preference" not in columns
    finally:
        engine.dispose()
