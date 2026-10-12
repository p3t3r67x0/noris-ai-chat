"""Reproduce the localhost active-path failure without touching its database."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from noris_ai.core.config import Settings
from noris_ai.main import create_app
from tests.integration.test_chat_websocket import AUTH, ORIGIN, Simulator

pytestmark = pytest.mark.integration


def test_pdf_migration_restores_active_path_and_uploads_without_losing_messages(
    migration_config: Config, llm_config: Settings, tmp_path: Path
) -> None:
    command.upgrade(migration_config, "0007_text_references")
    url = os.environ["NORIS_TEST_DATABASE_URL"]
    config = Settings(
        **(
            llm_config.model_dump()
            | {"database_url": url, "chat_attachment_storage_dir": str(tmp_path / "attachments")}
        )
    )
    conversation_id, message_id = uuid4(), uuid4()
    engine = create_engine(url)
    try:
        # Seed the historical schema directly; today's ORM also has learning fields.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO chat_conversation (id, owner_id, title, title_source, version) "
                    "VALUES (:id, :owner, 'Synthetic migration regression', 'fallback', 1)"
                ),
                {"id": conversation_id, "owner": config.chat_owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO chat_message (id, conversation_id, role, content, status) "
                    "VALUES (:id, :conversation, 'user', 'Synthetic preserved message', "
                    "'completed')"
                ),
                {"id": message_id, "conversation": conversation_id},
            )
            connection.execute(
                text("UPDATE chat_conversation SET active_leaf_message_id = :leaf WHERE id = :id"),
                {"leaf": message_id, "id": conversation_id},
            )
    finally:
        engine.dispose()

    endpoint = f"/api/v1/conversations/{conversation_id}/active-path?limit=50"
    with TestClient(
        create_app(config, provider=Simulator()),
        base_url="http://localhost:3000",
        raise_server_exceptions=False,
    ) as client:
        assert client.get("/api/v1/health/ready").status_code == 503
        response = client.get(endpoint, auth=AUTH, headers=ORIGIN)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert response.json()["error"]["message"] == "An internal error occurred"

    # Apply the existing additive migration, rather than masking a database error.
    command.upgrade(migration_config, "head")
    with TestClient(
        create_app(config, provider=Simulator()), base_url="http://localhost:3000"
    ) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        response = client.get(endpoint, auth=AUTH, headers=ORIGIN)
        assert response.status_code == 200, response.text
        assert response.json()["messages"][0]["content"] == "Synthetic preserved message"
        assert client.get("/api/v1/chat/attachments/limits", auth=AUTH).status_code == 200
        upload = client.post(
            "/api/v1/chat/attachments",
            params={"conversationId": str(conversation_id), "filename": "synthetic.txt"},
            content=b"Synthetic attachment after migration",
            headers=ORIGIN | {"content-type": "text/plain"},
            auth=AUTH,
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["status"] == "ready"
