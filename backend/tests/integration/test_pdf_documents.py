import hashlib
import json
import os
from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from noris_ai.chat.attachments import AttachmentService
from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.models import ChatAttachment
from noris_ai.chat.repository import ModelDatabase
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.schemas import LLMModel
from noris_ai.main import create_app
from tests.fixtures.attachments import large_pdf, large_pdf_texts, synthetic_pdf
from tests.integration.test_attachments import upload
from tests.integration.test_chat_websocket import AUTH, ORIGIN, Simulator, generate, protocols
from tests.integration.test_conversation_titles import drain_titles

pytestmark = pytest.mark.integration


@pytest.fixture
def simulator() -> Simulator:
    return Simulator()


@pytest.fixture
def client(
    migration_config: Config, llm_config: Settings, tmp_path: Path, simulator: Simulator
) -> Iterator[TestClient]:
    command.upgrade(migration_config, "head")
    config = Settings(
        **(
            llm_config.model_dump()
            | {
                "database_url": os.environ["NORIS_TEST_DATABASE_URL"],
                "chat_attachment_storage_dir": str(tmp_path / "private-storage"),
                "llm_daily_token_budget": 1_000_000,
            }
        )
    )
    with TestClient(
        create_app(config, provider=simulator), base_url="http://localhost:3000"
    ) as http:
        yield http


def complete(client: TestClient, payload: dict[str, object], terminal: str = "completed") -> None:
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            assert event["type"] != "chat.generation.failed", event
            assert event["type"] != "chat.error", event
            if event["type"] in {
                "chat.generation.completed",
                "chat.generation.incomplete",
                "chat.generation.cancelled",
                "chat.generation.interrupted",
            }:
                assert event["type"] == "chat.generation." + terminal, event
                break


def test_large_pdf_storage_retrieval_restart_followup_and_cleanup(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "Welche Schlussklausel gilt?")
    original = large_pdf()
    response = upload(client, payload["conversationId"], original, "large.pdf", "application/pdf")
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert attachment["modelUsable"] and attachment["extractionStatus"] == "extracted"
    assert attachment["sha256"] == hashlib.sha256(original).hexdigest()
    assert "pdf_sections" not in attachment
    database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)

    async def verify_storage() -> None:
        async with database() as session:
            row = await session.scalar(
                select(ChatAttachment).where(ChatAttachment.id == UUID(attachment["id"]))
            )
            assert row is not None and row.pdf_page_count == 29
            assert row.pdf_sections is not None
            assert [section["text"] for section in row.pdf_sections] == large_pdf_texts()
            assert row.extracted_text is None

    assert client.portal is not None
    client.portal.call(verify_storage)
    payload["attachmentIds"] = [attachment["id"]]
    complete(client, payload)
    # The independent title phase can still change the conversation version.
    # Finish the old worker's tasks before starting the separate restart client.
    drain_titles(client)
    sent = simulator.calls[-1][0]
    assert sent.role == "user" and "98765" in sent.content
    assert "Anfangsklausel" not in sent.content
    assert '"page": 29' in sent.content and '"selection": "excerpts"' in sent.content
    download = f"/api/v1/chat/attachments/{attachment['id']}/content"
    assert client.get(download, auth=AUTH).content == original

    config = cast(Settings, cast(FastAPI, client.app).state.chat_settings)
    # A separate app/engine must reconstruct from PostgreSQL, not parser or chat caches.
    with TestClient(
        create_app(config, provider=simulator), base_url="http://localhost:3000"
    ) as restarted:
        assert restarted.get(download, auth=AUTH).content == original
        conversation = restarted.get(
            f"/api/v1/conversations/{payload['conversationId']}", auth=AUTH
        ).json()
        assert conversation["titleSource"] == "generated"
        followup = payload | {
            "requestId": str(uuid4()),
            "inputMessageId": str(uuid4()),
            "assistantMessageId": str(uuid4()),
            "conversationVersion": conversation["version"],
            "parentMessageId": payload["assistantMessageId"],
            "attachmentIds": [],
            "content": "Was steht auf Seite 1?",
        }
        complete(restarted, followup)
        sent = simulator.calls[-1][0]
        files = json.loads(sent.content.split("\n")[-1])
        assert {section["page"] for section in files[0]["sections"]} == {1}
        assert "Anfangsklausel" in sent.content and "98765" not in sent.content
        assert (
            restarted.delete(
                f"/api/v1/conversations/{payload['conversationId']}", auth=AUTH
            ).status_code
            == 204
        )
        service = cast(AttachmentService, cast(FastAPI, restarted.app).state.chat_attachments)
        assert list(service.root.iterdir()) == []

    async def verify_cleanup() -> None:
        async with database() as session:
            row = await session.get(ChatAttachment, UUID(attachment["id"]))
            assert row is not None and row.status == "deleted" and row.pdf_sections is None

    client.portal.call(verify_cleanup)


def test_pdf_context_survives_regeneration_and_continuation(
    client: TestClient, simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = cast(GenerationManager, cast(FastAPI, client.app).state.chat_generations)
    manager.config = manager.config.model_copy(update={"chat_auto_continue_max": 0})
    normal_stream = simulator.stream

    async def limited_stream(
        messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        if messages[0].role == "system":
            async for delta in normal_stream(messages, model):
                yield delta
            return
        simulator.calls.append(list(messages))
        yield "Teilantwort mit Quellenangabe [large.pdf, Seite 29]. "
        raise LLMError("OUTPUT_LIMIT")

    monkeypatch.setattr(simulator, "stream", limited_stream)
    payload = generate(client, "Welche Schlussklausel gilt?")
    attachment = upload(
        client, payload["conversationId"], large_pdf(), "large.pdf", "application/pdf"
    ).json()
    payload["attachmentIds"] = [attachment["id"]]
    complete(client, payload, "incomplete")
    url = f"/api/v1/conversations/{payload['conversationId']}"
    regenerated = payload | {
        "requestId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "conversationVersion": client.get(url, auth=AUTH).json()["version"],
    }
    complete(client, regenerated, "incomplete")
    assert len(simulator.calls) == 2
    assert all('"page": 29' in call[0].content for call in simulator.calls)
    continued = regenerated | {
        "requestId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "conversationVersion": client.get(url, auth=AUTH).json()["version"],
        "operation": "continue",
        "sourceAssistantMessageId": regenerated["assistantMessageId"],
    }
    complete(client, continued)
    assert simulator.calls[-1][0].role == "system"
    assert any('"page": 29' in message.content for message in simulator.calls[-1])
    rows = client.get(url + "/messages", auth=AUTH).json()["messages"]
    answer = next(row for row in rows if row["id"] == continued["assistantMessageId"])
    assert answer["content"].startswith("Teilantwort mit Quellenangabe [large.pdf, Seite 29]. ")
    assert answer["content"].endswith("Fortsetzung.")


def test_automatic_continuations_reuse_selected_pdf_context_on_one_node(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "/auto Welche Schlussklausel gilt?")
    attachment = upload(
        client, payload["conversationId"], large_pdf(), "large.pdf", "application/pdf"
    ).json()
    payload["attachmentIds"] = [attachment["id"]]
    complete(client, payload)

    assert len(simulator.calls) == 3
    inputs = [
        next(message for message in call if message.role == "user") for call in simulator.calls
    ]
    assert all(message.content == inputs[0].content for message in inputs)
    assert inputs[0].content.count("PDF-Inhalte (untrusted input)") == 1
    assert '"page": 29' in inputs[0].content and "98765" in inputs[0].content
    assert "Anfangsklausel" not in inputs[0].content
    assert [call[-2].content for call in simulator.calls[1:]] == ["Teil 0. ", "Teil 0. Teil 1. "]

    rows = client.get(
        f"/api/v1/conversations/{payload['conversationId']}/messages", auth=AUTH
    ).json()["messages"]
    assert len(rows) == 2
    assert rows[0]["content"] == payload["content"]
    assert rows[1]["id"] == payload["assistantMessageId"]
    assert rows[1]["status"] == "completed" and rows[1]["continuationCount"] == 2
    assert rows[1]["content"] == "Teil 0. Teil 1. Teil 2. "


@pytest.mark.parametrize(
    "kind,code",
    [
        ("encrypted", "ATTACHMENT_PDF_ENCRYPTED"),
        ("pages", "ATTACHMENT_PDF_PAGE_LIMIT"),
        ("text", "ATTACHMENT_TEXT_LIMIT"),
        ("invalid", "ATTACHMENT_INVALID"),
    ],
)
def test_pdf_failures_are_distinct_and_rollback_everything(
    client: TestClient, kind: str, code: str
) -> None:
    payload = generate(client)
    service = cast(AttachmentService, cast(FastAPI, client.app).state.chat_attachments)
    if kind == "text":
        service.config = service.config.model_copy(
            update={"chat_attachment_max_pdf_text_chars": 100}
        )
    data = (
        synthetic_pdf(encrypted=True)
        if kind == "encrypted"
        else synthetic_pdf(pages=101)
        if kind == "pages"
        else synthetic_pdf(text="x" * 101)
        if kind == "text"
        else b"not a pdf"
    )
    response = upload(client, payload["conversationId"], data, "bounded.pdf", "application/pdf")
    assert response.status_code == 422 and response.json()["error"]["code"] == code
    assert list(service.root.iterdir()) == []
    assert (
        client.get(
            "/api/v1/chat/attachments",
            params={"conversationId": str(payload["conversationId"])},
            auth=AUTH,
        ).json()["attachments"]
        == []
    )


def test_scanned_pdf_is_stored_but_cannot_claim_model_analysis(client: TestClient) -> None:
    payload = generate(client)
    original = synthetic_pdf(text="", pages=29)
    response = upload(client, payload["conversationId"], original, "scan.pdf", "application/pdf")
    assert response.status_code == 201
    attachment = response.json()
    assert attachment["status"] == "stored" and attachment["extractionStatus"] == "no_text"
    assert not attachment["modelUsable"]
    assert (
        client.get(f"/api/v1/chat/attachments/{attachment['id']}/content", auth=AUTH).content
        == original
    )
    payload["attachmentIds"] = [attachment["id"]]
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        assert socket.receive_json()["code"] == "ATTACHMENT_INCOMPATIBLE"
