"""Expand/rollback preserves every seeded legacy chat row."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, func, inspect, select
from sqlalchemy.orm import Session

from noris_ai.chat.models import (
    ChatAttachment,
    ChatConversation,
    ChatDraft,
    ChatGeneration,
    ChatMessage,
    ChatStreamEvent,
    ChatUserPreferences,
)
from noris_ai.tools.models import ToolApproval, ToolResult, ToolRun

pytestmark = pytest.mark.integration
LEGACY_TABLES = (
    ChatConversation.__table__,
    ChatMessage.__table__,
    ChatGeneration.__table__,
    ChatAttachment.__table__,
    ChatStreamEvent.__table__,
    ChatDraft.__table__,
    ChatUserPreferences.__table__,
)


def legacy_rows(connection: Connection) -> list[list[tuple[object, ...]]]:
    return [
        [tuple(row) for row in connection.execute(select(table)).all()] for table in LEGACY_TABLES
    ]


def test_tool_upgrade_repeat_drift_and_rollback_preserve_legacy_data(
    migration_config: Config,
) -> None:
    command.upgrade(migration_config, "0010_conversation_learning")
    engine = create_engine(os.environ["NORIS_TEST_DATABASE_URL"])
    owner, conversation, message, generation = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        with Session(engine) as session, session.begin():
            chat = ChatConversation(
                id=conversation,
                owner_id=owner,
                title="Preserved generated title",
                title_source="generated",
                title_generation_claimed_at=datetime.now(UTC),
                conversation_mode="learning",
                reasoning_preference="high",
                version=7,
            )
            session.add(chat)
            session.flush()
            session.add(
                ChatMessage(
                    id=message,
                    conversation_id=conversation,
                    role="user",
                    content="Preserved history",
                    status="completed",
                )
            )
            session.flush()
            chat.active_leaf_message_id = message
            session.add(
                ChatGeneration(
                    id=generation,
                    conversation_id=conversation,
                    owner_id=owner,
                    input_message_id=message,
                    model_id="fixture-gpt-oss",
                    status="running",
                )
            )
            session.flush()
            session.add_all(
                [
                    ChatAttachment(
                        owner_id=owner,
                        conversation_id=conversation,
                        message_id=message,
                        original_filename="synthetic.pdf",
                        storage_key="synthetic-test-only-key",
                        mime_type="application/pdf",
                        size_bytes=100,
                        sha256="f" * 64,
                        status="ready",
                        extracted_text="Preserved PDF text",
                        pdf_page_count=1,
                        pdf_sections=[{"page": 1, "text": "Preserved PDF text"}],
                    ),
                    ChatStreamEvent(
                        generation_id=generation,
                        sequence=1,
                        event_type="chat.generation.started",
                        payload={"synthetic": True},
                    ),
                    ChatDraft(
                        owner_id=owner, draft_key=str(conversation), content="Preserved draft"
                    ),
                    ChatUserPreferences(
                        owner_id=owner, active_conversation_id=conversation, model_id="fixture-glm"
                    ),
                ]
            )
        with engine.connect() as connection:
            before = legacy_rows(connection)
        command.upgrade(migration_config, "head")
        command.upgrade(migration_config, "head")
        command.check(migration_config)
        with engine.connect() as connection:
            assert legacy_rows(connection) == before
            for model in (ToolRun, ToolResult, ToolApproval):
                assert connection.scalar(select(func.count()).select_from(model)) == 0
        assert {"chat_tool_run", "chat_tool_result", "chat_tool_approval"} <= set(
            inspect(engine).get_table_names()
        )
        command.downgrade(migration_config, "0010_conversation_learning")
        with engine.connect() as connection:
            assert legacy_rows(connection) == before
        assert "chat_tool_run" not in inspect(engine).get_table_names()
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    finally:
        engine.dispose()
