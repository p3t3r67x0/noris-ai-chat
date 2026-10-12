"""Prepared chats retain their input and become discoverable on every terminal state."""

from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import Settings
from tests.integration.test_chat_websocket import AUTH, ORIGIN, protocols
from tests.integration.test_conversation_titles import (
    TitleSimulator,
    client,
    drain_titles,
    simulator,
)

pytestmark = pytest.mark.integration
__all__ = ["client", "simulator"]


@pytest.mark.parametrize(
    "prompt,failure,model_id",
    [
        ("Erkläre mir SearXNG.", None, "fixture-alpha"),
        ("/error", None, "fixture-alpha"),
        ("Titelfehler", "TIMEOUT", "fixture-alpha"),
        ("Erkläre mir SearXNG.", None, "fixture-missing"),
    ],
)
def test_prepared_chat_terminal_visibility(
    client: TestClient,
    simulator: TitleSimulator,
    prompt: str,
    failure: str | None,
    model_id: str,
) -> None:
    simulator.title_failure = failure
    conversation_id = str(uuid4())
    create = {"id": conversation_id, "prepared": True}
    first = client.post("/api/v1/conversations", auth=AUTH, headers=ORIGIN.copy(), json=create)
    second = client.post("/api/v1/conversations", auth=AUTH, headers=ORIGIN.copy(), json=create)
    assert first.status_code == second.status_code == 201
    assert first.json()["sidebarVisible"] is False
    assert second.json()["id"] == conversation_id
    assert len(client.get("/api/v1/conversations", auth=AUTH).json()["conversations"]) == 1
    payload = {
        "version": 1,
        "type": "chat.generate",
        "requestId": str(uuid4()),
        "conversationId": conversation_id,
        "conversationVersion": 1,
        "inputMessageId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "modelId": model_id,
        "content": prompt,
    }
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            assert event["type"] != "chat.error", event
            if event["type"] in {"chat.generation.completed", "chat.generation.failed"}:
                break
        drain_titles(client)
    path = f"/api/v1/conversations/{conversation_id}"
    saved = client.get(path, auth=AUTH).json()
    assert saved["sidebarVisible"] is True
    assert saved["title"] != "Neuer Chat"
    response_failed = prompt == "/error" or model_id == "fixture-missing"
    assert saved["titleSource"] == ("fallback" if failure or response_failed else "generated")
    messages = client.get(path + "/messages", auth=AUTH).json()["messages"]
    assert messages[0]["content"] == prompt
    assert len(messages) == 2
    assert simulator.title_calls == (0 if response_failed else 1)


def test_prepared_chat_is_visible_after_startup_recovery(client: TestClient) -> None:
    app = cast(FastAPI, client.app)
    repository = cast(ChatRepository, app.state.chat_repository)
    owner = cast(Settings, app.state.chat_settings).chat_owner_id
    created = client.post("/api/v1/conversations", auth=AUTH, json={"prepared": True}).json()
    command = GenerateIncomingMessage(
        version=1,
        type="chat.generate",
        requestId=uuid4(),
        conversationId=UUID(created["id"]),
        conversationVersion=1,
        inputMessageId=uuid4(),
        assistantMessageId=uuid4(),
        modelId="fixture-alpha",
        content="Erkläre mir SearXNG.",
    )
    assert client.portal is not None
    client.portal.call(repository.begin_generation, owner, command)
    assert client.portal.call(repository.mark_running_generations_interrupted, owner) == 1
    saved = client.get(f"/api/v1/conversations/{created['id']}", auth=AUTH).json()
    assert saved["sidebarVisible"] is True
    assert saved["title"] == "SearXNG"
