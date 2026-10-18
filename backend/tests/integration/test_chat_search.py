"""Search against disposable PostgreSQL, through the authenticated existing API."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import Table, Text, bindparam, insert, literal_column, select, text, update
from sqlalchemy.schema import CreateIndex
from test_chat_api import AUTH, chat_app, chat_config, client, migrated

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.repository import ModelDatabase
from noris_ai.chat.search import fold, search_text
from noris_ai.chat.service import ChatService

__all__ = ["chat_app", "chat_config", "client", "migrated"]
pytestmark = pytest.mark.integration
OWNER = uuid.UUID(int=42)


async def add(
    app: FastAPI,
    title: str,
    contents: list[str],
    *,
    day: int = 1,
    owner: uuid.UUID = OWNER,
    archived: bool = False,
    pinned: bool = False,
    deleted: bool = False,
) -> tuple[str, list[str]]:
    database = cast(ModelDatabase, app.state.chat_database)
    conversation = uuid.uuid4()
    ids = [uuid.uuid4() for _ in contents]
    when = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day)
    async with database() as session, session.begin():
        await session.execute(
            insert(ChatConversation).values(
                id=conversation,
                owner_id=owner,
                title=title,
                title_source="manual",
                version=1,
                updated_at=when,
                archived_at=when if archived else None,
                pinned_at=when if pinned else None,
                deleted_at=when if deleted else None,
            )
        )
        for index, (message, content) in enumerate(zip(ids, contents, strict=True)):
            await session.execute(
                insert(ChatMessage).values(
                    id=message,
                    conversation_id=conversation,
                    parent_message_id=ids[index - 1] if index else None,
                    role="assistant" if index % 2 else "user",
                    content=content,
                    status="completed",
                    created_at=when + timedelta(seconds=index),
                )
            )
        if ids:
            await session.execute(
                update(ChatConversation)
                .where(ChatConversation.id == conversation)
                .values(active_leaf_message_id=ids[-1])
            )
    return str(conversation), [str(i) for i in ids]


async def search(
    client: AsyncClient, query: str = "", **filters: str | bool | int
) -> dict[str, Any]:
    response = await client.get("/api/v1/conversations", params={"q": query, **filters}, auth=AUTH)
    assert response.status_code == 200, response.text
    return response.json()


async def test_and_across_title_messages_and_phrase_rank_with_stable_seeks(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    split, _ = await add(chat_app, "Docker setup", ["Neutral", "healthcheck details"], day=9)
    across, _ = await add(chat_app, "Operations", ["Docker", "healthcheck"], day=8)
    exact, ids = await add(
        chat_app, "Older exact", ["docker healthcheck", "healthcheck later"], day=2
    )
    title, _ = await add(chat_app, "docker healthcheck", ["Neutral"], day=1)
    await add(chat_app, "Docker only", ["Missing second term"])
    expected = [exact, title, split, across]
    cursor = None
    found: list[str] = []
    snippets: list[dict[str, Any]] = []
    for _ in expected:
        page = await search(
            client, "Docker healthcheck", limit=1, **({"cursor": cursor} if cursor else {})
        )
        found += [row["id"] for row in page["conversations"]]
        snippets += page.get("matches", [])
        cursor = page["nextCursor"]
    assert found == expected and cursor is None
    assert (
        next(match for match in snippets if match["conversationId"] == exact)["messageId"] == ids[0]
    )
    assert all(match["conversationId"] != title for match in snippets)
    page = await search(client, "Docker healthcheck", limit=1)
    for params in [{"q": "healthcheck Docker"}, {"archiveFilter": "all"}, {"pinned": True}]:
        response = await client.get(
            "/api/v1/conversations",
            params={"q": "Docker healthcheck", "cursor": page["nextCursor"], **params},
            auth=AUTH,
        )
        assert response.status_code == 422


async def test_orthogonal_filters_and_legacy_archive_compatibility(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    combinations: dict[tuple[bool, bool], str] = {}
    for archived in (False, True):
        for pinned in (False, True):
            ident, _ = await add(
                chat_app, "filter match", ["Input"], archived=archived, pinned=pinned
            )
            combinations[archived, pinned] = ident
    for archive in ("active", "archived", "all"):
        for pin in (None, False, True):
            page = await search(
                client,
                "filter match",
                archiveFilter=archive,
                **({"pinned": pin} if pin is not None else {}),
            )
            expected = {
                ident
                for (a, p), ident in combinations.items()
                if (archive == "all" or a == (archive == "archived")) and (pin is None or p == pin)
            }
            assert {row["id"] for row in page["conversations"]} == expected
    assert len((await search(client, archived=True))["conversations"]) == 4
    assert len((await search(client, archiveOnly=True))["conversations"]) == 2
    assert len((await search(client, pinned=True))["conversations"]) == 1
    for legacy in ("archived", "archiveOnly"):
        response = await client.get(
            "/api/v1/conversations", params={"archiveFilter": "all", legacy: True}, auth=AUTH
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    ("content", "query"),
    [
        ("Straße ÄPFEL", "STRASSE A\u0308pfel"),
        ("ΟΣΟΣ", "οσος"),
        ("東京 healthcheck", "HEALTHCHECK\u3000東京"),
        ("가", "\u1100\u1161"),
        ("literal %_ \\ value", "%_ \\"),
        ("👩🏽‍💻", "👩"),
        ("\u037e", ";"),
        ("\u1fef", "`"),
    ],
)
async def test_unicode_and_literal_matching(
    client: AsyncClient, chat_app: FastAPI, content: str, query: str
) -> None:
    ident, _ = await add(chat_app, "Unicode fixture", ["x" * 300 + content])
    await add(chat_app, "No wildcard match", ["Plain text"])
    page = await search(client, query)
    assert [row["id"] for row in page["conversations"]] == [ident]
    assert page["matches"][0]["excerpt"].startswith("…")


async def test_isolation_deleted_empty_and_inactive_branch_targets(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    ident, messages = await add(chat_app, "Docker", ["Root", "Ordinary active answer"])
    database = cast(ModelDatabase, chat_app.state.chat_database)
    branch = uuid.uuid4()
    async with database() as session, session.begin():
        await session.execute(
            insert(ChatMessage).values(
                id=branch,
                conversation_id=uuid.UUID(ident),
                parent_message_id=uuid.UUID(messages[0]),
                role="assistant",
                status="completed",
                content="healthcheck alternative",
            )
        )
    await add(
        chat_app,
        "Docker healthcheck private marker",
        ["secret healthcheck"],
        owner=uuid.UUID(int=99),
    )
    await add(chat_app, "Docker healthcheck", ["deleted healthcheck"], deleted=True)
    await add(chat_app, "Docker healthcheck", [])
    page = await search(client, "Docker healthcheck", archiveFilter="all")
    assert [row["id"] for row in page["conversations"]] == [ident]
    assert page["matches"][0]["messageId"] == str(branch)
    assert "secret" not in str(page)
    target = await client.get(
        f"/api/v1/conversations/{ident}/active-path", params={"messageId": str(branch)}, auth=AUTH
    )
    assert target.status_code == 200 and target.json()["messages"][-1]["id"] == str(branch)
    assert (await search(client, "private marker", archiveFilter="all"))["conversations"] == []
    assert (await search(client, "%\"' OR true --", archiveFilter="all"))["conversations"] == []
    assert (
        await client.get("/api/v1/conversations", params={"q": "Docker healthcheck"})
    ).status_code == 401


async def test_limits_and_accent_distinction(client: AsyncClient, chat_app: FastAPI) -> None:
    await add(chat_app, "café", ["Input"])
    assert len((await search(client, "cafe"))["conversations"]) == 0
    for params in [
        {"q": "x" * 201},
        {"q": "\0"},
        {"q": " ".join(str(i) for i in range(33))},
        {"archiveFilter": "invalid"},
        {"pinned": "invalid"},
    ]:
        response = await client.get("/api/v1/conversations", params=params, auth=AUTH)
        assert response.status_code == 422


async def test_filtered_pages_snippets_and_cross_owner_cursor(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    expected: list[str] = []
    for day in range(1, 6):
        ident, _ = await add(
            chat_app, "Docker", [f"healthcheck {day}"], day=day, archived=True, pinned=True
        )
        expected.insert(0, ident)
    await add(chat_app, "Docker", ["healthcheck excluded active"], pinned=True)
    await add(chat_app, "Docker", ["healthcheck excluded unpinned"], archived=True)
    first = await search(
        client, "docker healthcheck", archiveFilter="archived", pinned=True, limit=2
    )
    second = await search(
        client,
        "docker healthcheck",
        archiveFilter="archived",
        pinned=True,
        limit=2,
        cursor=first["nextCursor"],
    )
    third = await search(
        client,
        "docker healthcheck",
        archiveFilter="archived",
        pinned=True,
        limit=2,
        cursor=second["nextCursor"],
    )
    pages = [first, second, third]
    assert [row["id"] for page in pages for row in page["conversations"]] == expected
    assert third["nextCursor"] is None
    for page in pages:
        assert {match["conversationId"] for match in page["matches"]} == {
            row["id"] for row in page["conversations"]
        }
        assert all("excluded" not in match["excerpt"] for match in page["matches"])
    service = cast(ChatService, chat_app.state.chat_service)
    with pytest.raises(ChatError) as error:
        await service.conversation_page(
            uuid.UUID(int=99),
            query="docker healthcheck",
            archive_filter="archived",
            pinned=True,
            cursor=first["nextCursor"],
        )
    assert error.value.code == "INVALID_CURSOR"


async def test_repeated_word_phrase_is_still_ranked(client: AsyncClient, chat_app: FastAPI) -> None:
    exact, _ = await add(chat_app, "Docker Docker", ["Neutral"], day=1)
    await add(chat_app, "Docker", ["Neutral"], day=9)
    page = await search(client, "docker docker")
    assert page["conversations"][0]["id"] == exact


async def test_search_index_migration_roundtrip_preserves_data(
    client: AsyncClient, chat_app: FastAPI, migration_config: Config
) -> None:
    ident, _ = await add(chat_app, "Straße", ["Äpfel"])
    await asyncio.to_thread(command.downgrade, migration_config, "0017_research_grounding")
    assert (await search(client, "strasse äpfel"))["conversations"][0]["id"] == ident
    await asyncio.to_thread(command.upgrade, migration_config, "head")
    assert (await search(client, "strasse äpfel"))["conversations"][0]["id"] == ident
    database = cast(ModelDatabase, chat_app.state.chat_database)
    async with database() as session:
        valid = (
            await session.execute(
                text(
                    "SELECT c.relname, i.indisvalid FROM pg_index i "
                    "JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname IN "
                    "('ix_chat_message_search_unicode','ix_chat_conversation_search_unicode')"
                )
            )
        ).all()
    assert len(valid) == 2 and all(row[1] for row in valid)
    # Compare PostgreSQL's parsed expressions, rather than SQL text formatting.
    # A mismatch would silently prevent the functional index from serving queries.
    async with database() as session:
        connection = await session.connection()
        for model in (ChatConversation, ChatMessage):
            table = cast(Table, model.__table__)
            for index in table.indexes:
                if index.name is None or not index.name.endswith("_search_unicode"):
                    continue
                fixture_name = f"fixture_{index.name}"
                column = "title" if model is ChatConversation else "content"
                query_expression = str(
                    search_text(literal_column(column, Text)).compile(dialect=connection.dialect)
                )
                ddls = (
                    str(CreateIndex(index).compile(dialect=connection.dialect)).replace(
                        index.name, fixture_name, 1
                    ),
                    f"CREATE INDEX {fixture_name} ON {table.name} "
                    f"USING gin (({query_expression}) gin_trgm_ops)",
                )
                for ddl in ddls:
                    await session.execute(text(ddl))
                    expressions = (
                        (
                            await session.execute(
                                text(
                                    "SELECT pg_get_expr(indexprs, indrelid) FROM pg_index "
                                    "JOIN pg_class ON pg_class.oid=indexrelid "
                                    "WHERE relname IN (:original, :fixture)"
                                ),
                                {"original": index.name, "fixture": fixture_name},
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert len(expressions) == 2 and expressions[0] == expressions[1]
                    await session.execute(text(f"DROP INDEX {fixture_name}"))


async def test_postgres_search_fold_matches_python(chat_app: FastAPI) -> None:
    database = cast(ModelDatabase, chat_app.state.chat_database)
    async with database() as session:
        for value in (
            "".join(chr(code) for code in range(1, 128)),
            "Straße",
            "\u1100\u1161",
            "\u037e\u1fef",
            "İ A\u0308 Σςσ",
            "ﬃ ꭰᎠ",
        ):
            actual = await session.scalar(select(search_text(bindparam("value"))), {"value": value})
            assert actual == fold(value)
