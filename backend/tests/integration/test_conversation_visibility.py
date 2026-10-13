"""Visibility comes from committed input, independent of title/drafts/uploads."""

import uuid
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import update
from test_chat_api import AUTH, chat_app, chat_config, client, migrated

from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.repository import ChatRepository, utc_now
from tests.fixtures.attachments import synthetic_pdf, synthetic_png

__all__ = ["chat_app", "chat_config", "client", "migrated"]
pytestmark = pytest.mark.integration
OWNER = uuid.UUID(int=42)


@pytest.mark.parametrize("prepared", [False, True])
async def test_empty_drafts_uploads_and_legacy_flags_stay_hidden(
    client: AsyncClient, chat_app: FastAPI, prepared: bool
) -> None:
    row = (
        await client.post("/api/v1/conversations", auth=AUTH, json={"prepared": prepared})
    ).json()
    id = row["id"]
    path = f"/api/v1/conversations/{id}"
    assert row["lifecycle"] == "EMPTY" and row["sidebarVisible"] is False
    assert (
        await client.put(path + "/draft", auth=AUTH, json={"content": "Unsent draft"})
    ).status_code == 200
    files: list[str] = []
    for filename, mime, data in [
        ("synthetic.png", "image/png", synthetic_png()),
        ("synthetic.pdf", "application/pdf", synthetic_pdf()),
    ]:
        upload = await client.post(
            "/api/v1/chat/attachments",
            params={"conversationId": id, "filename": filename},
            content=data,
            headers={"content-type": mime},
            auth=AUTH,
        )
        assert upload.status_code == 201, upload.text
        files.append(upload.json()["id"])
    failed = await client.post(
        "/api/v1/chat/attachments",
        params={"conversationId": id, "filename": "invalid.png"},
        content=b"Invalid image",
        headers={"content-type": "image/png"},
        auth=AUTH,
    )
    assert failed.status_code == 422
    repository = cast(ChatRepository, chat_app.state.chat_repository)
    # Reproduce historical rows marked visible by creation/title operations.
    async with repository.database() as session, session.begin():
        await session.execute(
            update(ChatConversation)
            .where(ChatConversation.id == uuid.UUID(id))
            .values(sidebar_visible=True)
        )
    renamed = (
        await client.patch(path, auth=AUTH, json={"title": "Manual empty title", "version": 1})
    ).json()
    assert renamed["sidebarVisible"] is False
    for params in [{}, {"q": "Manual"}, {"archived": "true"}, {"pinned": "false"}]:
        page = (await client.get("/api/v1/conversations", auth=AUTH, params=params)).json()
        assert page == {"conversations": [], "nextCursor": None, "hasMore": False}
    recovery = (await client.get("/api/v1/conversations?preparedOnly=true", auth=AUTH)).json()
    assert [c["id"] for c in recovery["conversations"]] == [id]
    archived = (await client.patch(path, auth=AUTH, json={"archived": True, "version": 2})).json()
    assert archived["sidebarVisible"] is False
    assert (await client.get("/api/v1/conversations?archiveOnly=true", auth=AUTH)).json()[
        "conversations"
    ] == []
    assert await repository.list_conversations(OWNER, include_archived=True) == []
    assert (await client.get(path, auth=AUTH)).json()["lifecycle"] == "EMPTY"
    drafts = (await client.get("/api/v1/chat/drafts", auth=AUTH)).json()["drafts"]
    assert any(d["key"] == id and d["content"] == "Unsent draft" for d in drafts)
    attachments = (
        await client.get("/api/v1/chat/attachments", auth=AUTH, params={"conversationId": id})
    ).json()["attachments"]
    assert {a["id"] for a in attachments} == set(files)


@pytest.mark.parametrize(
    "status,lifecycle",
    [
        (None, "STARTED"),
        ("pending", "GENERATING"),
        ("streaming", "GENERATING"),
        ("failed", "FAILED"),
        ("cancelled", "STARTED"),
        ("incomplete", "STARTED"),
        ("completed", "COMPLETED"),
    ],
)
async def test_persisted_input_is_visible_in_every_lifecycle_without_a_title(
    client: AsyncClient, chat_app: FastAPI, status: str | None, lifecycle: str
) -> None:
    row = (await client.post("/api/v1/conversations", auth=AUTH, json={"prepared": True})).json()
    repository = cast(ChatRepository, chat_app.state.chat_repository)
    id, message = uuid.UUID(row["id"]), uuid.uuid4()
    await repository.append_user_message(
        OWNER, id, message_id=message, parent_message_id=None, content="Persisted input"
    )
    if status:
        await repository.append_message(
            ChatMessage(
                id=uuid.uuid4(),
                conversation_id=id,
                parent_message_id=message,
                role="assistant",
                content="",
                status=status,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
    saved = (await client.get(f"/api/v1/conversations/{id}", auth=AUTH)).json()
    assert saved["lifecycle"] == lifecycle and saved["sidebarVisible"] is True
    assert saved["title"] == "Neuer Chat"
    for params in [{}, {"q": "Neuer Chat"}, {"archived": "true"}]:
        assert [
            c["id"]
            for c in (await client.get("/api/v1/conversations", auth=AUTH, params=params)).json()[
                "conversations"
            ]
        ] == [str(id)]
    assert (await client.get("/api/v1/conversations?preparedOnly=true", auth=AUTH)).json()[
        "conversations"
    ] == []
    assert len(await repository.list_conversations(OWNER, include_archived=True)) == 1
    assert (
        await client.patch(
            f"/api/v1/conversations/{id}", auth=AUTH, json={"archived": True, "version": 1}
        )
    ).status_code == 200
    assert (await client.get("/api/v1/conversations", auth=AUTH)).json()["conversations"] == []
    assert [
        c["id"]
        for c in (await client.get("/api/v1/conversations?archiveOnly=true", auth=AUTH)).json()[
            "conversations"
        ]
    ] == [str(id)]
