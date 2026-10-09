"""Integration tests for the chat REST API against real PostgreSQL."""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app

pytestmark = pytest.mark.integration

AUTH = ("fixture-user", "fixture-application-password-never-real")


@pytest.fixture
def chat_config(monkeypatch: pytest.MonkeyPatch) -> EnvironmentSettings:
    url = os.environ.get("NORIS_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set NORIS_TEST_DATABASE_URL to a disposable PostgreSQL test database")
    monkeypatch.setenv("NORIS_DATABASE_URL", url)
    monkeypatch.setenv("NORIS_ENVIRONMENT", "test")
    return EnvironmentSettings(
        environment="test",
        llm_provider="openai-compatible",
        llm_base_url="http://127.0.0.1:9999/v1",
        llm_allowed_hosts=("127.0.0.1",),
        llm_api_key=SecretStr("fixture-provider-key-never-real"),
        llm_access_username="fixture-user",
        llm_access_password=SecretStr("fixture-application-password-never-real"),
        llm_allowed_origins=("http://localhost:3000",),
        chat_owner_id=uuid.UUID(int=42),
    )


@pytest.fixture
def migrated(chat_config: EnvironmentSettings, migration_config: Config) -> None:
    command.upgrade(migration_config, "head")


@pytest.fixture
async def chat_app(migrated: None, chat_config: EnvironmentSettings) -> AsyncGenerator[FastAPI]:
    app = create_app(settings=chat_config)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(chat_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=chat_app), base_url="http://test") as http:
        yield http


async def test_conversation_crud_and_versioning(client: AsyncClient) -> None:
    created = await client.post("/api/v1/conversations", json={"title": "Thema"}, auth=AUTH)
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["title"] == "Thema"
    assert conversation["titleSource"] == "fallback"
    assert conversation["version"] == 1

    listed = await client.get("/api/v1/conversations", auth=AUTH)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["conversations"]] == [conversation["id"]]

    renamed = await client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Manuell", "version": 1},
        auth=AUTH,
    )
    assert renamed.status_code == 200
    assert renamed.json()["titleSource"] == "manual"
    assert renamed.json()["version"] == 2

    stale = await client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Nochmal", "version": 1},
        auth=AUTH,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    archived = await client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"archived": True, "version": 2},
        auth=AUTH,
    )
    assert archived.status_code == 200
    assert archived.json()["archivedAt"] is not None
    assert (await client.get("/api/v1/conversations", auth=AUTH)).json()["conversations"] == []
    archived_list = await client.get("/api/v1/conversations?archived=true", auth=AUTH)
    assert len(archived_list.json()["conversations"]) == 1

    deleted = await client.delete(f"/api/v1/conversations/{conversation['id']}", auth=AUTH)
    assert deleted.status_code == 204
    response = await client.get(f"/api/v1/conversations/{conversation['id']}", auth=AUTH)
    assert response.status_code == 404


async def test_access_control(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/conversations")).status_code == 401
    denied = await client.get("/api/v1/conversations", auth=("fixture-user", "wrong-password"))
    assert denied.status_code == 401
    response = await client.post(
        "/api/v1/conversations",
        json={"title": "X"},
        auth=AUTH,
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_DENIED"


def _tree_payload(conversation_id: uuid.UUID) -> dict[str, object]:
    now = datetime.now(UTC)
    user_id, assistant_id = uuid.uuid4(), uuid.uuid4()
    return {
        "conversations": [
            {
                "id": str(conversation_id),
                "title": "Importierter Chat",
                "titleSource": "manual",
                "createdAt": (now - timedelta(minutes=5)).isoformat(),
                "updatedAt": now.isoformat(),
                "archivedAt": None,
                "activeLeafMessageId": str(assistant_id),
                "version": 1,
            }
        ],
        "messages": [
            {
                "id": str(user_id),
                "conversationId": str(conversation_id),
                "parentMessageId": None,
                "role": "user",
                "content": "Frage",
                "status": "completed",
                "modelId": None,
                "editedFromMessageId": None,
                "createdAt": (now - timedelta(minutes=4)).isoformat(),
                "updatedAt": (now - timedelta(minutes=4)).isoformat(),
            },
            {
                "id": str(assistant_id),
                "conversationId": str(conversation_id),
                "parentMessageId": str(user_id),
                "role": "assistant",
                "content": "Antwort",
                "status": "completed",
                "modelId": "fixture-alpha",
                "editedFromMessageId": None,
                "createdAt": (now - timedelta(minutes=3)).isoformat(),
                "updatedAt": (now - timedelta(minutes=3)).isoformat(),
            },
        ],
        "drafts": {str(conversation_id): "Entwurf"},
        "activeConversationId": str(conversation_id),
    }


async def test_import_is_idempotent_and_reports_conflicts(client: AsyncClient) -> None:
    conversation_id = uuid.uuid4()
    payload: dict[str, object] = _tree_payload(conversation_id)
    first = await client.post("/api/v1/conversations/import", json=payload, auth=AUTH)
    assert first.status_code == 200, first.text
    assert first.json()["imported"] == [str(conversation_id)]
    assert first.json()["draftsImported"] == 1

    again = await client.post("/api/v1/conversations/import", json=payload, auth=AUTH)
    assert again.status_code == 200
    assert again.json()["skipped"] == [str(conversation_id)]
    assert again.json()["imported"] == []

    messages = await client.get(f"/api/v1/conversations/{conversation_id}/messages", auth=AUTH)
    assert messages.status_code == 200
    roles = [message["role"] for message in messages.json()["messages"]]
    assert roles == ["user", "assistant"]

    conversations = cast("list[dict[str, object]]", payload["conversations"])
    conversations[0]["title"] = "Geändert"
    conflict = await client.post("/api/v1/conversations/import", json=payload, auth=AUTH)
    assert conflict.status_code == 200
    assert conflict.json()["conflicts"] == [
        {"conversationId": str(conversation_id), "reason": "exists_with_different_data"}
    ]


async def test_drafts_and_preferences(client: AsyncClient) -> None:
    conversation = (await client.post("/api/v1/conversations", json={}, auth=AUTH)).json()
    draft = await client.put(
        f"/api/v1/conversations/{conversation['id']}/draft",
        json={"content": "Entwurftext"},
        auth=AUTH,
    )
    assert draft.status_code == 200
    drafts = (await client.get("/api/v1/chat/drafts", auth=AUTH)).json()["drafts"]
    assert {item["key"]: item["content"] for item in drafts} == {
        str(conversation["id"]): "Entwurftext"
    }
    preferences = await client.put(
        "/api/v1/chat/preferences",
        json={"activeConversationId": conversation["id"], "modelId": "fixture-alpha"},
        auth=AUTH,
    )
    assert preferences.status_code == 200
    assert preferences.json() == {
        "activeConversationId": conversation["id"],
        "modelId": "fixture-alpha",
    }
    unknown = await client.put(
        "/api/v1/chat/preferences",
        json={"activeConversationId": str(uuid.uuid4())},
        auth=AUTH,
    )
    assert unknown.status_code == 404


async def test_generated_titles_never_overwrite_manual(
    client: AsyncClient, chat_app: FastAPI
) -> None:
    from noris_ai.chat.service import ChatService

    conversation = (await client.post("/api/v1/conversations", json={}, auth=AUTH)).json()
    app = chat_app
    service = cast(ChatService, app.state.chat_service)
    owner = cast(EnvironmentSettings, app.state.chat_settings).chat_owner_id

    manual = await client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Manueller Titel", "version": 1},
        auth=AUTH,
    )
    assert manual.json()["titleSource"] == "manual"

    await service.apply_generated_title(owner, uuid.UUID(conversation["id"]), "KI Titel")
    refreshed = await client.get(f"/api/v1/conversations/{conversation['id']}", auth=AUTH)
    assert refreshed.json()["title"] == "Manueller Titel"

    second = (
        await client.post("/api/v1/conversations", json={"title": "Fallback"}, auth=AUTH)
    ).json()
    await service.apply_generated_title(owner, uuid.UUID(second["id"]), "KI Titel")
    generated = await client.get(f"/api/v1/conversations/{second['id']}", auth=AUTH)
    assert generated.json()["title"] == "KI Titel"
    assert generated.json()["titleSource"] == "generated"
