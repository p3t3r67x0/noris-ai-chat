"""Durable titles over the real WebSocket protocol and disposable PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.repository import ChatRepository, ModelDatabase
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import LLMModel
from noris_ai.llm.titles import TitleInstruction
from tests.fixtures.provider_catalog import provider_model
from tests.integration.test_chat_websocket import (
    AUTH,
    ORIGIN,
    Simulator,
    client,
    generate,
    protocols,
)

pytestmark = pytest.mark.integration
__all__ = ["client"]  # Reuse the migrated, isolated TestClient fixture.


class TitleSimulator(Simulator):
    def __init__(self) -> None:
        super().__init__()
        self.title_calls = 0
        self.title_failure: str | None = None
        self.invalid_title = False

    async def discover_models(self) -> list[ProviderModel]:
        return [
            provider_model(value)
            for value in [
                "fixture-alpha",
                "vllm/qsu/deepseek-v41-flash",
                "vllm/release/gpt-oss-120b",
            ]
        ]

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        if isinstance(messages[0], TitleInstruction):
            self.title_calls += 1
            await asyncio.sleep(0.1)  # Allow a real manual rename during generation.
            if self.title_failure:
                raise LLMError(self.title_failure)
            yield "invalid" if self.invalid_title else "Persistente Gespräche"
            return
        async for delta in super().stream(messages, model):
            yield delta


@pytest.fixture
def simulator() -> TitleSimulator:
    return TitleSimulator()


def drain_titles(http: TestClient) -> None:
    manager = cast(GenerationManager, cast(FastAPI, http.app).state.chat_generations)

    async def wait() -> None:
        await asyncio.wait_for(asyncio.gather(*list(manager.tasks)), 3)

    assert http.portal is not None
    http.portal.call(wait)


def completed(socket: WebSocketTestSession) -> None:
    while True:
        event = socket.receive_json()
        assert event["type"] not in {"chat.error", "chat.generation.failed"}, event
        if event["type"] == "chat.generation.completed":
            return


@pytest.mark.parametrize("model_id", ["vllm/qsu/deepseek-v41-flash", "vllm/release/gpt-oss-120b"])
def test_title_commits_broadcasts_to_two_tabs_and_survives_reconnect(
    client: TestClient,
    simulator: TitleSimulator,
    model_id: str,
) -> None:
    payload = generate(client) | {"modelId": model_id}
    with (
        client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as first,
        client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as second,
    ):
        first.receive_json()
        second.receive_json()
        first.send_json(payload)
        completed(first)
        for socket in [first, second]:
            while True:
                event = socket.receive_json()
                if event["type"] == "chat.title.updated":
                    assert event["titleSource"] == "generated"
                    assert event["title"] == "Persistente Gespräche"
                    break
        drain_titles(client)
    path = f"/api/v1/conversations/{payload['conversationId']}"
    saved = client.get(path, auth=AUTH).json()
    assert saved["titleSource"] == "generated"
    assert saved["title"] == "Persistente Gespräche"
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as resumed:
        resumed.receive_json()
        resumed.send_json(
            {
                "version": 1,
                "type": "chat.resume",
                "generationId": payload["requestId"],
                "lastReceivedSeq": 0,
            }
        )
        completed(resumed)
        assert client.get(path, auth=AUTH).json()["title"] == saved["title"]
    assert simulator.title_calls == 1
    # Regenerate the first answer: only the chat provider call may repeat.
    current = client.get(path, auth=AUTH).json()
    retry = payload | {
        "requestId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "conversationVersion": current["version"],
        "operation": "generate",
    }
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(retry)
        completed(socket)
        drain_titles(client)
    assert simulator.title_calls == 1


@pytest.mark.parametrize("failure", ["TIMEOUT", "BUDGET_LIMIT", "RATE_LIMIT", "INVALID_RESPONSE"])
def test_title_failure_keeps_completed_answer_and_claim_without_provider_retry(
    client: TestClient,
    simulator: TitleSimulator,
    failure: str,
) -> None:
    simulator.title_failure = failure
    payload = generate(client)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        completed(socket)
        drain_titles(client)
    path = f"/api/v1/conversations/{payload['conversationId']}"
    assert client.get(path, auth=AUTH).json()["titleSource"] == "fallback"
    messages = client.get(path + "/messages", auth=AUTH).json()["messages"]
    assert messages[-1]["status"] == "completed" and messages[-1]["errorCode"] is None
    repository = cast(ChatRepository, cast(FastAPI, client.app).state.chat_repository)
    owner = cast(Settings, cast(FastAPI, client.app).state.chat_settings).chat_owner_id
    assert client.portal is not None
    assert (
        client.portal.call(
            repository.claim_generated_title, owner, UUID(str(payload["conversationId"]))
        )
        is False
    )
    assert simulator.title_calls == 1


def test_manual_rename_during_title_call_wins(
    client: TestClient, simulator: TitleSimulator
) -> None:
    payload = generate(client)
    path = f"/api/v1/conversations/{payload['conversationId']}"
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        completed(socket)
        current = client.get(path, auth=AUTH).json()
        response = client.patch(
            path,
            auth=AUTH,
            headers=ORIGIN.copy(),
            json={"title": "Manueller Titel", "version": current["version"]},
        )
        assert response.status_code == 200
        drain_titles(client)
    saved = client.get(path, auth=AUTH).json()
    assert saved["title"] == "Manueller Titel" and saved["titleSource"] == "manual"


def test_atomic_claim_and_idempotent_persistence_across_repository_instances(
    client: TestClient,
) -> None:
    payload = generate(client)
    database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)
    owner = cast(Settings, cast(FastAPI, client.app).state.chat_settings).chat_owner_id
    conversation_id = UUID(str(payload["conversationId"]))

    async def race() -> None:
        first, second = ChatRepository(database), ChatRepository(database)
        claims = await asyncio.gather(
            first.claim_generated_title(owner, conversation_id),
            second.claim_generated_title(owner, conversation_id),
        )
        assert sorted(claims) == [False, True]
        await first.set_generated_title(owner, conversation_id, "Erster Titel")
        result = await second.set_generated_title(owner, conversation_id, "Zweiter Titel")
        assert result is not None and result.title == "Erster Titel"
        assert result.version == 2
        # A fresh instance observes the durable claim, as after a restart.
        assert await ChatRepository(database).claim_generated_title(owner, conversation_id) is False

    assert client.portal is not None
    client.portal.call(race)


def test_manual_rename_broadcasts_versioned_metadata_to_all_tabs(client: TestClient) -> None:
    payload = generate(client)
    path = f"/api/v1/conversations/{payload['conversationId']}"
    with (
        client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as first,
        client.websocket_connect(
            "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
        ) as second,
    ):
        first.receive_json()
        second.receive_json()
        response = client.patch(
            path, auth=AUTH, headers=ORIGIN.copy(), json={"title": "Manueller Titel", "version": 1}
        )
        assert response.status_code == 200
        for socket in [first, second]:
            event = socket.receive_json()
            assert event["type"] == "chat.conversation.updated"
            assert event["conversation"]["titleSource"] == "manual"
            assert event["conversation"]["title"] == "Manueller Titel"
            assert event["conversation"]["version"] == 2
