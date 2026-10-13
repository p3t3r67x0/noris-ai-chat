"""Conversation pins use the existing owner/version contract and independent seeks."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from test_chat_api import AUTH, chat_app, chat_config, client, migrated

from noris_ai.chat.models import ChatConversation
from noris_ai.chat.repository import ModelDatabase
from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app

__all__ = ["chat_app", "chat_config", "client", "migrated"]
pytestmark = pytest.mark.integration
OWNER = uuid.UUID(int=42)


async def create(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/conversations", json={"title": "Synthetic pin"}, auth=AUTH
    )
    assert response.status_code == 201
    return response.json()


async def test_pin_idempotence_unpin_and_backend_restart(
    client: AsyncClient, chat_config: EnvironmentSettings
) -> None:
    row = await create(client)
    path = f"/api/v1/conversations/{row['id']}"
    assert row["pinnedAt"] is None
    pinned = (await client.patch(path, json={"pinned": True, "version": 1}, auth=AUTH)).json()
    assert pinned["pinnedAt"] and pinned["version"] == 2
    assert pinned["updatedAt"] == row["updatedAt"]
    assert pinned["title"] == row["title"] and pinned["activeLeafMessageId"] is None
    repeated = await client.patch(path, json={"pinned": True, "version": 2}, auth=AUTH)
    assert repeated.json() == pinned
    # A fresh application and connection pool see the same PostgreSQL authority.
    restarted = create_app(settings=chat_config)
    async with (
        restarted.router.lifespan_context(restarted),
        AsyncClient(transport=ASGITransport(app=restarted), base_url="http://test") as http,
    ):
        assert (await http.get(path, auth=AUTH)).json() == pinned
    unpinned = await client.patch(path, json={"pinned": False, "version": 2}, auth=AUTH)
    assert unpinned.json()["pinnedAt"] is None and unpinned.json()["version"] == 3
    assert (
        await client.patch(path, json={"pinned": False, "version": 3}, auth=AUTH)
    ).json() == unpinned.json()


async def test_local_import_preserves_pins_without_overwriting_existing_chats(
    client: AsyncClient,
) -> None:
    id = str(uuid.uuid4())
    snapshot: dict[str, object] = {
        "conversations": [
            {
                "id": id,
                "title": "Imported local pin",
                "titleSource": "manual",
                "createdAt": "2020-01-01T00:00:00Z",
                "updatedAt": "2020-01-01T00:00:00Z",
                "pinnedAt": "2026-10-12T12:00:00Z",
            }
        ],
        "messages": [],
        "drafts": {},
    }
    imported = await client.post("/api/v1/conversations/import", json=snapshot, auth=AUTH)
    assert imported.status_code == 200 and imported.json()["imported"] == [id]
    row = (await client.get(f"/api/v1/conversations/{id}", auth=AUTH)).json()
    assert datetime.fromisoformat(row["pinnedAt"]) == datetime(2026, 10, 12, 12, tzinfo=UTC)
    repeated = await client.post("/api/v1/conversations/import", json=snapshot, auth=AUTH)
    assert repeated.json()["skipped"] == [id]
    await client.patch(
        f"/api/v1/conversations/{id}", json={"pinned": False, "version": 1}, auth=AUTH
    )
    conflict = await client.post("/api/v1/conversations/import", json=snapshot, auth=AUTH)
    assert conflict.json()["conflicts"][0]["reason"] == "exists_with_different_data"
    assert (await client.get(f"/api/v1/conversations/{id}", auth=AUTH)).json()["pinnedAt"] is None


async def test_pin_owner_deleted_and_invalid_updates(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    row = await create(client)
    foreign = uuid.uuid4()
    database = cast(ModelDatabase, chat_app.state.chat_database)
    async with database() as session, session.begin():
        session.add(
            ChatConversation(
                id=foreign, owner_id=uuid.uuid4(), title="Foreign", title_source="manual", version=1
            )
        )
    for id in [foreign, uuid.uuid4()]:
        assert (
            await client.patch(
                f"/api/v1/conversations/{id}", json={"pinned": True, "version": 1}, auth=AUTH
            )
        ).status_code == 404
    path = f"/api/v1/conversations/{row['id']}"
    for payload in [
        {"pinned": None, "version": 1},
        {"pinned": True},
        {"pinned": True, "archived": True, "version": 1},
    ]:
        assert (await client.patch(path, json=payload, auth=AUTH)).status_code == 422
    assert (await client.delete(path, auth=AUTH)).status_code == 204
    assert (
        await client.patch(path, json={"pinned": True, "version": 1}, auth=AUTH)
    ).status_code == 404


async def test_concurrent_pin_updates_preserve_revision(client: AsyncClient) -> None:
    row = await create(client)
    responses = await asyncio.gather(
        *[
            client.patch(
                f"/api/v1/conversations/{row['id']}", json={"pinned": True, "version": 1}, auth=AUTH
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (await client.get(f"/api/v1/conversations/{row['id']}", auth=AUTH)).json()[
        "version"
    ] == 2


async def test_independent_pinned_seek_is_stable_scoped_and_finds_old_chats(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    database = cast(ModelDatabase, chat_app.state.chat_database)
    now = datetime.now(UTC)
    async with database() as session, session.begin():
        await session.execute(
            insert(ChatConversation),
            [
                dict(
                    id=uuid.UUID(int=1000 + i),
                    owner_id=OWNER,
                    title=f"Synthetic {i}",
                    title_source="manual",
                    version=1,
                    updated_at=now - timedelta(days=200 + i),
                    pinned_at=now - timedelta(seconds=i // 3),
                    archived_at=None,
                )
                for i in range(123)
            ]
            + [
                dict(
                    id=uuid.uuid4(),
                    owner_id=OWNER,
                    title="Recent",
                    title_source="manual",
                    version=1,
                    updated_at=now,
                    pinned_at=None,
                    archived_at=None,
                )
            ],
        )
    first = (await client.get("/api/v1/conversations?pinned=true&limit=10", auth=AUTH)).json()
    rows = first["conversations"][:]
    cursor = first["nextCursor"]
    while cursor:
        page = (
            await client.get(
                "/api/v1/conversations",
                params={"pinned": "true", "limit": 10, "cursor": cursor},
                auth=AUTH,
            )
        ).json()
        rows.extend(page["conversations"])
        cursor = page["nextCursor"]
    assert len(rows) == 123 and len({r["id"] for r in rows}) == 123
    assert [r["id"] for r in rows[:6]] == [
        str(uuid.UUID(int=i)) for i in [1002, 1001, 1000, 1005, 1004, 1003]
    ]
    regular = (await client.get("/api/v1/conversations?pinned=false", auth=AUTH)).json()[
        "conversations"
    ]
    assert len(regular) == 1 and regular[0]["title"] == "Recent"
    for params in [{"pinned": "false"}, {}, {"pinned": "true", "q": "Synthetic"}]:
        assert (
            await client.get(
                "/api/v1/conversations", params={**params, "cursor": first["nextCursor"]}, auth=AUTH
            )
        ).status_code == 422
    # Default search still includes both pinned and regular conversations.
    assert (await client.get("/api/v1/conversations?q=Synthetic&limit=100", auth=AUTH)).json()[
        "hasMore"
    ]


async def test_pins_hide_archives_and_deleted_rows(client: AsyncClient) -> None:
    row = await create(client)
    path = f"/api/v1/conversations/{row['id']}"
    await client.patch(path, json={"pinned": True, "version": 1}, auth=AUTH)
    await client.patch(path, json={"archived": True, "version": 2}, auth=AUTH)
    assert (await client.get("/api/v1/conversations?pinned=true&archived=true", auth=AUTH)).json()[
        "conversations"
    ] == []
    await client.patch(path, json={"archived": False, "version": 3}, auth=AUTH)
    assert (
        len(
            (await client.get("/api/v1/conversations?pinned=true", auth=AUTH)).json()[
                "conversations"
            ]
        )
        == 1
    )
    await client.delete(path, auth=AUTH)
    assert (await client.get("/api/v1/conversations?pinned=true", auth=AUTH)).json()[
        "conversations"
    ] == []


def test_pin_migration_preserves_existing_rows(migration_config: Config) -> None:
    import os

    import psycopg

    command.upgrade(migration_config, "0012_conversation_visibility")
    url = os.environ["NORIS_TEST_DATABASE_URL"].replace("postgresql+psycopg:", "postgresql:")
    with psycopg.connect(url) as connection:
        connection.execute(
            "INSERT INTO chat_conversation (id, owner_id, title, title_source, version) "
            "VALUES (%s, %s, 'Before migration', 'manual', 1)",
            (uuid.UUID(int=1), OWNER),
        )
    command.upgrade(migration_config, "head")
    with psycopg.connect(url) as connection:
        assert connection.execute(
            "SELECT title, pinned_at, sidebar_visible FROM chat_conversation"
        ).fetchone() == (
            "Before migration",
            None,
            True,
        )
        assert connection.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='chat_conversation' AND column_name='pinned_at'"
        ).fetchone() == ("timestamp with time zone",)
        assert connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname='ix_chat_conversation_pinned_seek'"
        ).fetchone()
    command.downgrade(migration_config, "0012_conversation_visibility")
    command.upgrade(migration_config, "head")
