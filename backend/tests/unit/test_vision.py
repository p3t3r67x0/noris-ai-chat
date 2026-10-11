import base64
import hashlib
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from noris_ai.chat.attachment_parser import prepare_image
from noris_ai.core.config import Settings
from noris_ai.llm.continuation import continuation_messages
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.provider import provider_payload
from noris_ai.llm.schemas import ChatRequest, LLMMessage, PersistedChatRequest
from noris_ai.llm.tokens import TokenCounter
from noris_ai.llm.vision import IMAGE_MAX_EDGE, IMAGE_TOKEN_RESERVE, VisionImage, VisionMessage
from tests.fixtures.attachments import synthetic_png
from tests.fixtures.provider_catalog import provider_data


def image_message(tmp_path: Path) -> VisionMessage:
    data = synthetic_png()
    path = tmp_path / "synthetic.png"
    path.write_bytes(data)
    url = prepare_image(path, "image/png", 16_000_000, len(data), hashlib.sha256(data).hexdigest())
    return VisionMessage(
        role="user", content="Describe this synthetic image", images=(VisionImage(data_url=url),)
    )


def request(message: LLMMessage) -> PersistedChatRequest:
    return PersistedChatRequest(
        generationId="vision-generation",
        conversationId="conversation",
        inputMessageId="input",
        modelId="fixture-alpha",
        messages=[message],
        attempt=1,
    )


def test_normalization_limits_dimensions_and_removes_metadata(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.jpg"
    source = Image.new("RGB", (2048, 1024), "white")
    exif = Image.Exif()
    exif[270] = "Synthetic private metadata must never reach the provider"
    source.save(path, format="JPEG", exif=exif)
    data = path.read_bytes()
    url = prepare_image(path, "image/jpeg", 16_000_000, len(data), hashlib.sha256(data).hexdigest())
    image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert image.size == (IMAGE_MAX_EDGE, IMAGE_MAX_EDGE // 2)
    assert not image.getexif()
    assert path.read_bytes() == data


def test_changed_bytes_and_symlinked_storage_cannot_be_forwarded(tmp_path: Path) -> None:
    data = synthetic_png()
    path = tmp_path / "synthetic.png"
    path.write_bytes(data)
    with pytest.raises(ValueError, match="Storage integrity"):
        prepare_image(path, "image/png", 1000, len(data), "0" * 64)
    link = tmp_path / "symlink"
    link.symlink_to(path)
    with pytest.raises(OSError):
        prepare_image(link, "image/png", 1000, len(data), hashlib.sha256(data).hexdigest())


def test_public_rest_contract_remains_text_only_and_internal_data_stays_private(
    tmp_path: Path,
) -> None:
    message = image_message(tmp_path)
    payload = request(message)
    assert isinstance(payload.messages[0], VisionMessage)
    assert "data:image" not in payload.model_dump_json()
    assert "data:image" not in repr(message)
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload.model_dump() | {"messages": [provider_payload(message)]})
    with pytest.raises(ValidationError):
        VisionMessage(role="assistant", content="response", images=message.images)


def test_image_tokens_are_reserved_even_with_text_tokenization(
    tmp_path: Path, llm_config: Settings
) -> None:
    message = image_message(tmp_path)
    counter = TokenCounter(llm_config)
    plain = LLMMessage(role="user", content=message.content)
    assert (
        counter.estimate([message], "fixture-alpha")
        == counter.estimate([plain], "fixture-alpha") + IMAGE_TOKEN_RESERVE
    )
    continued = request(message).model_copy(
        update={
            "messages": [message, LLMMessage(role="assistant", content="An unfinished answer")],
            "operation": "continue",
            "assistantMessageId": "answer",
            "continuationCount": 1,
        }
    )
    assert continuation_messages(continued)[1] is message


async def test_documented_multimodal_payload_streams_without_a_live_provider(
    tmp_path: Path, llm_config: Settings
) -> None:
    captured: list[httpx.Request] = []

    def handler(upstream: httpx.Request) -> httpx.Response:
        if upstream.method == "GET":
            return httpx.Response(200, json={"data": [provider_data("fixture-alpha", vision=True)]})
        captured.append(upstream)
        content = (
            b'data: {"choices":[{"index":0,"delta":{"content":"Synthetic image response"},'
            b'"finish_reason":null}]}\n\n'
        )
        content += (
            b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    provider = OpenAICompatibleProvider(llm_config, transport=httpx.MockTransport(handler))
    gateway = LLMGateway(llm_config, provider)
    message = image_message(tmp_path)
    payload = request(message)
    try:
        await gateway.reserve(payload)
        events = [event async for event in gateway.events(payload)]
    finally:
        await provider.aclose()
    last = events[-1]
    assert last is not None and last.type == "response.completed"
    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["messages"] == [provider_payload(message)]
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )
    assert body["max_tokens"] == llm_config.llm_models[0].max_output_tokens


@pytest.mark.parametrize("failure", ["modality", "context", "bytes", "budget"])
async def test_image_admission_rejects_incompatible_or_over_budget_requests_before_post(
    tmp_path: Path, llm_config: Settings, failure: str
) -> None:
    captured: list[httpx.Request] = []

    def handler(upstream: httpx.Request) -> httpx.Response:
        captured.append(upstream)
        return httpx.Response(
            200, json={"data": [provider_data("fixture-alpha", vision=failure != "modality")]}
        )

    updates: dict[str, object] = {}
    if failure == "bytes":
        updates["llm_max_request_bytes"] = 1024
    if failure == "budget":
        updates["llm_daily_token_budget"] = IMAGE_TOKEN_RESERVE
    config = llm_config.model_copy(update=updates)
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(handler))
    gateway = LLMGateway(config, provider)
    message = image_message(tmp_path)
    if failure == "context":
        message = message.model_copy(update={"images": message.images * 2})
    expected = {
        "modality": "MODEL_UNAVAILABLE",
        "context": "CONTEXT_LIMIT",
        "bytes": "REQUEST_TOO_LARGE",
        "budget": "BUDGET_LIMIT",
    }[failure]
    try:
        with pytest.raises(LLMError) as error:
            await gateway.reserve(request(message))
        assert error.value.code == expected
        assert all(upstream.method == "GET" for upstream in captured)
    finally:
        await provider.aclose()
