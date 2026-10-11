import asyncio
import io
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update

from noris_ai.chat.attachments import AttachmentService
from noris_ai.chat.models import ChatAttachment
from noris_ai.chat.repository import ModelDatabase
from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.provider import provider_payload
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.vision import VisionMessage
from noris_ai.main import create_app
from tests.fixtures.attachments import synthetic_pdf, synthetic_png
from tests.fixtures.provider_catalog import provider_model
from tests.integration.test_chat_websocket import AUTH, ORIGIN, Simulator, generate, protocols

pytestmark = pytest.mark.integration


@pytest.fixture
def simulator() -> Simulator:
    class VisionSimulator(Simulator):
        async def discover_models(self) -> list[ProviderModel]:
            return [provider_model("fixture-alpha"), provider_model("fixture-beta", vision=True)]

    return VisionSimulator()


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
                "chat_attachment_max_file_bytes": 2048,
                "chat_attachment_owner_quota_bytes": 4096,
                "chat_attachment_max_files": 2,
            }
        )
    )
    with TestClient(
        create_app(config, provider=simulator), base_url="http://localhost:3000"
    ) as http:
        yield http


def upload(
    client: TestClient,
    conversation_id: object,
    data: bytes = b"Synthetic attachment content",
    filename: str = "synthetic.txt",
    mime: str = "text/plain",
):
    return client.post(
        "/api/v1/chat/attachments",
        params={"conversationId": str(conversation_id), "filename": filename},
        content=data,
        headers=ORIGIN | {"content-type": mime},
        auth=AUTH,
    )


def test_upload_auth_storage_reload_download_and_removal(client: TestClient) -> None:
    payload = generate(client)
    assert (
        client.post(
            "/api/v1/chat/attachments",
            params={"conversationId": str(payload["conversationId"]), "filename": "synthetic.txt"},
            content=b"test",
            headers={"content-type": "text/plain"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/chat/attachments",
            params={"conversationId": str(payload["conversationId"]), "filename": "synthetic.txt"},
            content=b"test",
            headers={"content-type": "text/plain", "origin": "https://evil.example"},
            auth=AUTH,
        ).status_code
        == 403
    )
    response = upload(client, payload["conversationId"])
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["status"] == "ready" and value["modelUsable"] is True
    assert "storage_key" not in value and "extracted_text" not in value
    assert len(value["sha256"]) == 64
    restored = client.get(
        "/api/v1/chat/attachments",
        params={"conversationId": str(payload["conversationId"])},
        auth=AUTH,
    )
    assert restored.json()["attachments"] == [value]
    path = f"/api/v1/chat/attachments/{value['id']}/content"
    assert client.get(path).status_code == 401
    downloaded = client.get(path, auth=AUTH)
    assert downloaded.content == b"Synthetic attachment content"
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    storage = Path(
        cast(Settings, cast(FastAPI, client.app).state.chat_settings).chat_attachment_storage_dir
    )
    stored = list(storage.iterdir())
    assert len(stored) == 1 and len(stored[0].name) == 32
    assert stored[0].stat().st_mode & 0o777 == 0o600
    assert client.delete(f"/api/v1/chat/attachments/{value['id']}", auth=AUTH).status_code == 204
    assert client.get(path, auth=AUTH).status_code == 404
    assert list(storage.iterdir()) == []


@pytest.mark.parametrize(
    "filename,mime,data,status",
    [
        ("../evil.txt", "text/plain", b"test", 415),
        ("synthetic.zip", "application/zip", b"PK fake zip", 415),
        ("synthetic.txt", "text/plain", b"\xff\x00", 422),
        ("synthetic.pdf", "application/pdf", b"not a pdf", 422),
        ("synthetic.png", "image/png", b"not a png", 422),
        ("synthetic.txt", "text/plain", b"", 413),
        ("synthetic.txt", "text/plain", b"x" * 2049, 413),
    ],
)
def test_invalid_uploads_leave_no_metadata_or_files(
    client: TestClient, filename: str, mime: str, data: bytes, status: int
) -> None:
    payload = generate(client)
    assert upload(client, payload["conversationId"], data, filename, mime).status_code == status
    assert (
        client.get(
            "/api/v1/chat/attachments",
            params={"conversationId": str(payload["conversationId"])},
            auth=AUTH,
        ).json()["attachments"]
        == []
    )
    storage = Path(
        cast(Settings, cast(FastAPI, client.app).state.chat_settings).chat_attachment_storage_dir
    )
    assert not storage.exists() or list(storage.iterdir()) == []


def test_owned_image_preview_is_normalized_and_preserves_the_original(client: TestClient) -> None:
    payload = generate(client)
    original = synthetic_png(40, 20)
    attachment = upload(
        client, payload["conversationId"], original, "synthetic.png", "image/png"
    ).json()
    path = f"/api/v1/chat/attachments/{attachment['id']}/content"
    assert client.get(path, params={"preview": True}).status_code == 401
    preview = client.get(path, params={"preview": True}, auth=AUTH)
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    assert preview.headers["content-disposition"] == "inline"
    assert preview.headers["cache-control"] == "private, no-store"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.headers["content-security-policy"] == "sandbox; default-src 'none'"
    with Image.open(io.BytesIO(preview.content)) as image:
        image.load()
        assert image.format == "JPEG" and image.size == (40, 20)
        assert not image.getexif()
    assert client.get(path, auth=AUTH).content == original
    assert (
        client.delete(f"/api/v1/chat/attachments/{attachment['id']}", auth=AUTH).status_code == 204
    )
    assert client.get(path, params={"preview": True}, auth=AUTH).status_code == 404


def test_non_images_cannot_be_served_as_inline_previews(client: TestClient) -> None:
    payload = generate(client)
    attachment = upload(client, payload["conversationId"]).json()
    path = f"/api/v1/chat/attachments/{attachment['id']}/content"
    assert client.get(path, params={"preview": True}, auth=AUTH).status_code == 415
    assert client.get(path, auth=AUTH).content == b"Synthetic attachment content"


def test_pending_count_and_owner_storage_quotas(client: TestClient) -> None:
    first = generate(client)
    for _ in range(2):
        assert upload(client, first["conversationId"], b"x" * 2000).status_code == 201
    assert upload(client, first["conversationId"]).status_code == 413
    second = generate(client)
    assert upload(client, second["conversationId"], b"x" * 100).status_code == 413


def test_pdf_extraction_and_image_storage_do_not_authorize_text_only_models(
    client: TestClient,
) -> None:
    payload = generate(client)
    pdf = upload(
        client, payload["conversationId"], synthetic_pdf(), "synthetic.pdf", "application/pdf"
    )
    assert pdf.status_code == 201, pdf.text
    assert pdf.json()["extractionStatus"] == "extracted"
    image = upload(client, payload["conversationId"], synthetic_png(), "synthetic.png", "image/png")
    assert image.status_code == 201
    assert image.json()["status"] == "stored" and image.json()["modelUsable"] is True
    assert image.json()["extractionStatus"] == "not_applicable"
    payload["attachmentIds"] = [image.json()["id"]]
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        assert socket.receive_json()["code"] == "ATTACHMENT_INCOMPATIBLE"

    # A corrupt row cannot route image data through the text contract, even with vision.
    payload["modelId"] = "fixture-beta"
    database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)

    async def inconsistent_extraction() -> None:
        async with database() as session, session.begin():
            await session.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id == UUID(image.json()["id"]))
                .values(status="ready", extracted_text="Synthetic invalid image extraction")
            )

    assert client.portal is not None
    client.portal.call(inconsistent_extraction)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        assert socket.receive_json()["code"] == "ATTACHMENT_INCOMPATIBLE"


def test_websocket_binding_reconstructs_context_and_preserves_download_after_reload(
    client: TestClient,
    simulator: Simulator,
) -> None:
    payload = generate(client, "Summarize synthetic file")
    attached = upload(client, payload["conversationId"]).json()
    payload["attachmentIds"] = [attached["id"]]
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while socket.receive_json()["type"] != "chat.generation.completed":
            pass
    assert len(simulator.calls) == 1
    assert simulator.calls[0][0].role == "user"
    assert "Synthetic attachment content" in simulator.calls[0][0].content
    assert "untrusted input" in simulator.calls[0][0].content
    service = cast(AttachmentService, cast(FastAPI, client.app).state.chat_attachments)
    path = client.get(
        f"/api/v1/conversations/{payload['conversationId']}/active-path", auth=AUTH
    ).json()
    assert path["messages"][0]["attachments"][0]["id"] == attached["id"]
    assert path["messages"][0]["content"] == "Summarize synthetic file"
    assert client.delete(f"/api/v1/chat/attachments/{attached['id']}", auth=AUTH).status_code == 409
    assert (
        service.path(next(iter(service.root.iterdir())).name).read_bytes()
        == b"Synthetic attachment content"
    )
    assert (
        client.delete(f"/api/v1/conversations/{payload['conversationId']}", auth=AUTH).status_code
        == 204
    )
    assert list(service.root.iterdir()) == []


def test_image_provider_input_and_history_survive_reload_without_websocket_binary(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "Describe synthetic pixels") | {"modelId": "fixture-beta"}
    original = synthetic_png()
    attached = upload(
        client, payload["conversationId"], original, "synthetic.png", "image/png"
    ).json()
    payload["attachmentIds"] = [attached["id"]]
    path = f"/api/v1/conversations/{payload['conversationId']}"
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            assert "data:image" not in str(event)
            if event["type"] == "chat.generation.completed":
                break
    sent = simulator.calls[-1][0]
    assert isinstance(sent, VisionMessage)
    assert provider_payload(sent)["role"] == "user"
    assert sent.images[0].data_url.startswith("data:image/jpeg;base64,")
    messages = client.get(path + "/messages", auth=AUTH).json()["messages"]
    assert messages[0]["attachments"][0]["id"] == attached["id"]
    assert (
        client.get(f"/api/v1/chat/attachments/{attached['id']}/content", auth=AUTH).content
        == original
    )
    assert (
        client.get(
            f"/api/v1/chat/attachments/{attached['id']}/content",
            params={"preview": True},
            auth=AUTH,
        ).status_code
        == 200
    )

    # Restored history cannot silently drop its image when a text model is chosen.
    conversation = client.get(path, auth=AUTH).json()
    followup = payload | {
        "requestId": str(uuid4()),
        "inputMessageId": str(uuid4()),
        "assistantMessageId": str(uuid4()),
        "parentMessageId": payload["assistantMessageId"],
        "conversationVersion": conversation["version"],
        "modelId": "fixture-alpha",
        "content": "Follow up",
        "attachmentIds": [],
    }
    before = len(simulator.calls)
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(followup)
        assert socket.receive_json()["code"] == "ATTACHMENT_INCOMPATIBLE"
    assert len(simulator.calls) == before

    # A compatible follow-up receives the original image again from owned storage.
    followup["modelId"] = "fixture-beta"
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(followup)
        while socket.receive_json()["type"] != "chat.generation.completed":
            pass
    assert isinstance(simulator.calls[-1][0], VisionMessage)


def test_tampered_image_storage_fails_before_provider_generation(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "Describe synthetic pixels") | {"modelId": "fixture-beta"}
    attached = upload(
        client, payload["conversationId"], synthetic_png(), "synthetic.png", "image/png"
    ).json()
    service = cast(AttachmentService, cast(FastAPI, client.app).state.chat_attachments)
    next(service.root.iterdir()).write_bytes(b"Synthetic storage tampering")
    assert (
        client.get(
            f"/api/v1/chat/attachments/{attached['id']}/content",
            params={"preview": True},
            auth=AUTH,
        ).status_code
        == 422
    )
    payload["attachmentIds"] = [attached["id"]]
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            if event["type"] == "chat.generation.failed":
                assert event["code"] == "ATTACHMENT_INVALID"
                break
    assert not simulator.calls


def test_attachment_ownership_conversation_and_orphan_cleanup(client: TestClient) -> None:
    payload = generate(client)
    attachment = upload(client, payload["conversationId"]).json()
    other = generate(client)
    other["attachmentIds"] = [attachment["id"]]
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(other)
        assert socket.receive_json()["code"] == "ATTACHMENT_NOT_FOUND"
    database = cast(ModelDatabase, cast(FastAPI, client.app).state.chat_database)
    service = cast(AttachmentService, cast(FastAPI, client.app).state.chat_attachments)

    async def change_owner() -> None:
        async with database() as session, session.begin():
            await session.execute(
                update(ChatAttachment)
                .where(ChatAttachment.id == UUID(attachment["id"]))
                .values(owner_id=uuid4())
            )

    assert client.portal is not None
    client.portal.call(change_owner)
    assert (
        client.get(f"/api/v1/chat/attachments/{attachment['id']}/content", auth=AUTH).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/chat/attachments/{attachment['id']}/content",
            params={"preview": True},
            auth=AUTH,
        ).status_code
        == 404
    )

    async def expire() -> None:
        async with database() as session, session.begin():
            row = await session.scalar(
                select(ChatAttachment).where(ChatAttachment.id == UUID(attachment["id"]))
            )
            assert row is not None
            row.owner_id = cast(
                Settings, cast(FastAPI, client.app).state.chat_settings
            ).chat_owner_id
            row.created_at = datetime.now(UTC) - timedelta(hours=25)
        await service.cleanup()

    assert client.portal is not None
    client.portal.call(expire)
    assert list(service.root.iterdir()) == []
    assert (
        client.get(f"/api/v1/chat/attachments/{attachment['id']}/content", auth=AUTH).status_code
        == 404
    )


def test_aborted_stream_rolls_back_and_releases_quota(client: TestClient) -> None:
    payload = generate(client)
    app = cast(FastAPI, client.app)
    service = cast(AttachmentService, app.state.chat_attachments)
    config = cast(Settings, app.state.chat_settings)

    async def abort() -> None:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"Synthetic partial upload"
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await service.upload(
                config.chat_owner_id,
                UUID(str(payload["conversationId"])),
                "synthetic.txt",
                "text/plain",
                chunks(),
            )

    assert client.portal is not None
    client.portal.call(abort)
    assert list(service.root.iterdir()) == []
    assert upload(client, payload["conversationId"]).status_code == 201


def test_restart_restores_pending_metadata_and_private_storage(client: TestClient) -> None:
    payload = generate(client)
    value = upload(client, payload["conversationId"]).json()
    config = cast(Settings, cast(FastAPI, client.app).state.chat_settings)
    with TestClient(
        create_app(config, provider=Simulator()), base_url="http://localhost:3000"
    ) as restarted:
        restored = restarted.get(
            "/api/v1/chat/attachments",
            params={"conversationId": str(payload["conversationId"])},
            auth=AUTH,
        )
        assert restored.json()["attachments"] == [value]
        assert (
            restarted.get(f"/api/v1/chat/attachments/{value['id']}/content", auth=AUTH).content
            == b"Synthetic attachment content"
        )


def test_extracted_text_counts_against_existing_request_limit(
    client: TestClient, simulator: Simulator
) -> None:
    payload = generate(client, "Short question")
    value = upload(client, payload["conversationId"], b"x" * 1000).json()
    payload["attachmentIds"] = [value["id"]]
    gateway = cast(LLMGateway, cast(FastAPI, client.app).state.llm_gateway)
    gateway.config = gateway.config.model_copy(update={"llm_max_message_chars": 100})
    with client.websocket_connect(
        "/api/v1/chat/ws", subprotocols=protocols(client), headers=ORIGIN.copy()
    ) as socket:
        socket.receive_json()
        socket.send_json(payload)
        while True:
            event = socket.receive_json()
            if event["type"] == "chat.generation.failed":
                assert event["code"] == "REQUEST_TOO_LARGE"
                break
    assert not simulator.calls
