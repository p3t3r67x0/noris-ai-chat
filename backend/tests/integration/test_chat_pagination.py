"""Real PostgreSQL seeks, scoped cursors and lazy immutable branches."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import insert, text, update
from test_chat_api import AUTH, chat_app, chat_config, client, migrated

from noris_ai.chat.cursors import Cursor
from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.repository import ModelDatabase
from noris_ai.chat.schemas import MessageRole
from noris_ai.chat.service import ChatService
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.llm.schemas import LLMMessage, PersistedChatRequest

# Reuse the fixture definitions, not a second application/database architecture.
__all__ = ["chat_app", "chat_config", "client", "migrated"]
pytestmark = pytest.mark.integration
OWNER = uuid.UUID(int=42)


async def seed(chat_app: FastAPI, count: int = 123) -> list[uuid.UUID]:
    database = cast(ModelDatabase, chat_app.state.chat_database)
    ids = [uuid.UUID(int=1000 + i) for i in range(count)]
    async with database() as session, session.begin():
        await session.execute(
            insert(ChatConversation),
            [
                dict(
                    id=id,
                    owner_id=OWNER,
                    title=f"Synthetic {index}",
                    title_source="manual",
                    version=1,
                    updated_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index // 3),
                    archived_at=datetime.now(UTC) if index % 10 == 0 else None,
                )
                for index, id in enumerate(ids)
            ],
        )
        await session.execute(
            insert(ChatConversation).values(
                id=uuid.uuid4(),
                owner_id=uuid.uuid4(),
                title="Foreign",
                title_source="manual",
                version=1,
            )
        )
    return ids


async def test_stable_conversation_seeks_search_archives_and_scope(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    ids = await seed(chat_app)
    first = (await client.get("/api/v1/conversations?archived=true", auth=AUTH)).json()
    assert len(first["conversations"]) == 50 and first["hasMore"]
    rows = first["conversations"][:]
    cursor = first["nextCursor"]
    while cursor:
        response = await client.get(
            "/api/v1/conversations", params={"archived": "true", "cursor": cursor}, auth=AUTH
        )
        assert response.status_code == 200
        page = response.json()
        rows.extend(page["conversations"])
        cursor = page["nextCursor"]
    assert [r["id"] for r in rows] == [str(i) for i in reversed(ids)]
    assert len({r["id"] for r in rows}) == len(ids)
    for invalid in ["!!!", first["nextCursor"] + "=", "x" * 2049]:
        assert (
            await client.get("/api/v1/conversations", params={"cursor": invalid}, auth=AUTH)
        ).status_code == 422
    assert (
        await client.get("/api/v1/conversations", params={"cursor": first["nextCursor"]}, auth=AUTH)
    ).status_code == 422
    for limit in [0, 101, -1]:
        assert (
            await client.get("/api/v1/conversations", params={"limit": limit}, auth=AUTH)
        ).status_code == 422
    active = (await client.get("/api/v1/conversations", auth=AUTH)).json()["conversations"]
    assert all(r["archivedAt"] is None for r in active)
    archived = (await client.get("/api/v1/conversations?archiveOnly=true", auth=AUTH)).json()[
        "conversations"
    ]
    assert len(archived) == 13 and all(r["archivedAt"] for r in archived)
    found = (
        await client.get(
            "/api/v1/conversations", params={"q": "Synthetic 1", "archived": "true"}, auth=AUTH
        )
    ).json()["conversations"]
    assert all("Synthetic 1" in r["title"] for r in found)
    assert (await client.get("/api/v1/conversations?q=%25", auth=AUTH)).json()[
        "conversations"
    ] == []
    assert (await client.get("/api/v1/conversations?q=Foreign&archived=true", auth=AUTH)).json()[
        "conversations"
    ] == []


async def test_thousand_message_branch_windows_variants_and_complete_provider_context(
    client: AsyncClient,
    chat_app: FastAPI,
) -> None:
    app = chat_app
    database = cast(ModelDatabase, app.state.chat_database)
    service = cast(ChatService, app.state.chat_service)
    conversation = uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(1002)]
    variant = uuid.uuid4()
    now = datetime.now(UTC)
    async with database() as session, session.begin():
        await session.execute(
            insert(ChatConversation).values(
                id=conversation, owner_id=OWNER, title="Long", title_source="manual", version=1
            )
        )
        # Parent-before-child order is enforced by the real database triggers.
        for i, id in enumerate(ids):
            await session.execute(
                insert(ChatMessage).values(
                    id=id,
                    conversation_id=conversation,
                    parent_message_id=ids[i - 1] if i else None,
                    role="assistant" if i % 2 else "user",
                    content=f"Node {i}",
                    status="completed",
                    created_at=now + timedelta(microseconds=i),
                )
            )
        await session.execute(
            insert(ChatMessage).values(
                id=variant,
                conversation_id=conversation,
                parent_message_id=ids[998],
                role="assistant",
                content="Alternative",
                status="completed",
                created_at=now + timedelta(seconds=1),
            )
        )
        await session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation)
            .values(active_leaf_message_id=ids[-1])
        )
    url = f"/api/v1/conversations/{conversation}/active-path"
    response = await client.get(url, auth=AUTH)
    assert response.status_code == 200, response.text
    page = response.json()
    assert len(page["messages"]) == 50 and page["hasMore"]
    assert page["messages"][0]["parentMessageId"] == str(ids[-51])
    summaries = {r["messageId"]: r for r in page["variants"]}
    assert summaries[str(ids[999])]["total"] == 2
    assert summaries[str(ids[999])]["nextMessageId"] == str(variant)
    all_ids = [m["id"] for m in page["messages"]]
    cursor = page["nextCursor"]
    while cursor:
        earlier = (await client.get(url, params={"cursor": cursor}, auth=AUTH)).json()
        assert earlier["leafMessageId"] == str(ids[-1])
        all_ids = [m["id"] for m in earlier["messages"]] + all_ids
        cursor = earlier["nextCursor"]
    assert all_ids == [str(id) for id in ids]
    branch = (await client.get(url, params={"messageId": str(variant)}, auth=AUTH)).json()
    assert branch["leafMessageId"] == str(variant)
    assert branch["messages"][-1]["content"] == "Alternative"
    preferred = (
        await client.get(
            url, params={"messageId": str(ids[999]), "preferredLeafId": str(ids[-1])}, auth=AUTH
        )
    ).json()
    assert preferred["leafMessageId"] == str(ids[-1])
    bad = Cursor(
        scope=f"path:{OWNER}:{conversation}", id=variant, leaf=ids[-1], revision=1
    ).encode()
    assert (await client.get(url, params={"cursor": bad}, auth=AUTH)).status_code == 422
    assert (
        await client.get(url, params={"messageId": str(uuid.uuid4())}, auth=AUTH)
    ).status_code == 422
    await client.patch(
        f"/api/v1/conversations/{conversation}",
        json={"activeLeafMessageId": str(variant), "version": 1},
        auth=AUTH,
    )
    assert (
        await client.get(url, params={"cursor": page["nextCursor"]}, auth=AUTH)
    ).status_code == 409
    # Generation must load every selected ancestor, never just the UI window.
    await client.patch(
        f"/api/v1/conversations/{conversation}",
        json={"activeLeafMessageId": str(ids[-1]), "version": 2},
        auth=AUTH,
    )
    command = GenerateIncomingMessage.model_validate(
        dict(
            version=1,
            type="chat.generate",
            requestId=str(uuid.uuid4()),
            conversationId=str(conversation),
            inputMessageId=str(uuid.uuid4()),
            assistantMessageId=str(uuid.uuid4()),
            modelId="fixture-alpha",
            conversationVersion=3,
            content="Next",
            parentMessageId=str(ids[-1]),
            attempt=1,
        )
    )
    _, path, fresh = await service.repository.begin_generation(OWNER, command)
    assert fresh and len(path) == 1003
    assert [m.id for m in path[:-1]] == ids
    request = PersistedChatRequest(
        generationId="g",
        conversationId="c",
        inputMessageId="i",
        modelId="fixture-alpha",
        attempt=1,
        messages=[LLMMessage(role=cast(MessageRole, m.role), content=m.content) for m in path],
    )
    assert len(request.messages) == 1003
    # Chronological pages explicitly report a partial tree and never lose IDs.
    messages: list[dict[str, Any]] = []
    cursor = None
    while True:
        params = {"limit": 200, **({"cursor": cursor} if cursor else {})}
        result = (
            await client.get(
                f"/api/v1/conversations/{conversation}/messages", params=params, auth=AUTH
            )
        ).json()
        assert result["completeTree"] is False
        messages.extend(result["messages"])
        cursor = result["nextCursor"]
        if not cursor:
            break
    assert len(messages) == 1005 and len({m["id"] for m in messages}) == 1005
    assert (await client.get(url, params={"limit": 201}, auth=AUTH)).status_code == 422
    assert (
        await client.get(f"/api/v1/conversations/{uuid.uuid4()}/messages", auth=AUTH)
    ).status_code == 404


async def test_pagination_indexes_exist(client: AsyncClient, chat_app: FastAPI) -> None:
    await seed(chat_app, 3)
    database = cast(ModelDatabase, chat_app.state.chat_database)
    async with database() as session:
        indexes = (
            (
                await session.execute(
                    text("SELECT indexname FROM pg_indexes WHERE indexname LIKE '%seek'")
                )
            )
            .scalars()
            .all()
        )
    assert {
        "ix_chat_conversation_seek",
        "ix_chat_conversation_active_seek",
        "ix_chat_message_seek",
    } <= set(indexes)
