"""Integration coverage for the Etappe 3 chat persistence schema."""

import asyncio
import uuid
from collections.abc import Coroutine
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from noris_ai.core.config import Settings

pytestmark = pytest.mark.integration


def _run(coroutine: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coroutine)


def _database_url() -> str:
    return Settings().database_url.get_secret_value()


async def _insert_chat_tree(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    conversation, user_message, assistant_message = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO chat_conversation (id, owner_id, title, title_source, version)"
                " VALUES (:id, :owner, 'Thema', 'fallback', 1)"
            ),
            {"id": conversation, "owner": uuid.uuid4()},
        )
        await connection.execute(
            text(
                "INSERT INTO chat_message (id, conversation_id, parent_message_id, role,"
                " content, status) VALUES (:id, :c, NULL, 'user', 'Frage', 'completed')"
            ),
            {"id": user_message, "c": conversation},
        )
        await connection.execute(
            text(
                "INSERT INTO chat_message (id, conversation_id, parent_message_id, role,"
                " content, status) VALUES (:id, :c, :p, 'assistant', 'Antwort', 'completed')"
            ),
            {"id": assistant_message, "c": conversation, "p": user_message},
        )
        await connection.execute(
            text("UPDATE chat_conversation SET active_leaf_message_id = :leaf WHERE id = :id"),
            {"leaf": assistant_message, "id": conversation},
        )
    return conversation, user_message, assistant_message


def test_message_tree_and_active_leaf(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")

    async def run() -> None:
        engine = create_async_engine(_database_url())
        try:
            conversation, _, assistant_message = await _insert_chat_tree(engine)
            async with engine.connect() as connection:
                leaf = await connection.scalar(
                    text("SELECT active_leaf_message_id FROM chat_conversation WHERE id = :id"),
                    {"id": conversation},
                )
                assert leaf == assistant_message
        finally:
            await engine.dispose()

    _run(run())


def test_foreign_keys_reject_cross_conversation_parent(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")

    async def run() -> None:
        engine = create_async_engine(_database_url())
        try:
            conversation, _, _ = await _insert_chat_tree(engine)
            other_conversation = uuid.uuid4()
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO chat_conversation (id, owner_id, title, title_source,"
                        " version) VALUES (:id, :owner, 'Anders', 'fallback', 1)"
                    ),
                    {"id": other_conversation, "owner": uuid.uuid4()},
                )
            async with engine.begin() as connection:
                with pytest.raises(IntegrityError):
                    await connection.execute(
                        text(
                            "INSERT INTO chat_message (id, conversation_id, parent_message_id,"
                            " role, content, status) VALUES (:id, :c, :p, 'user', 'X',"
                            " 'completed')"
                        ),
                        {"id": uuid.uuid4(), "c": other_conversation, "p": conversation},
                    )
        finally:
            await engine.dispose()

    _run(run())


def test_stream_event_sequence_unique(migration_config: Config) -> None:
    command.upgrade(migration_config, "head")

    async def run() -> None:
        engine = create_async_engine(_database_url())
        try:
            conversation, user_message, assistant_message = await _insert_chat_tree(engine)
            generation = uuid.uuid4()
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO chat_generation (id, conversation_id, input_message_id,"
                        " assistant_message_id, owner_id, model_id, status, attempt,"
                        " last_sequence) VALUES (:id, :c, :i, :a, :owner, 'm', 'running', 1, 0)"
                    ),
                    {
                        "id": generation,
                        "c": conversation,
                        "i": user_message,
                        "a": assistant_message,
                        "owner": uuid.uuid4(),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO chat_stream_event (generation_id, sequence, event_type,"
                        " payload) VALUES (:g, 1, 'delta', '{\"text\":\"a\"}')"
                    ),
                    {"g": generation},
                )
            async with engine.begin() as connection:
                with pytest.raises(IntegrityError):
                    await connection.execute(
                        text(
                            "INSERT INTO chat_stream_event (generation_id, sequence,"
                            " event_type, payload) VALUES (:g, 1, 'delta', '{}')"
                        ),
                        {"g": generation},
                    )
        finally:
            await engine.dispose()

    _run(run())
