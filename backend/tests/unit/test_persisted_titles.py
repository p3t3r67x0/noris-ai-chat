"""Title failures must never change an already committed answer."""

# pyright: reportPrivateUsage=false

import asyncio
import json
import logging
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from noris_ai.chat.generation import GenerationManager
from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.openai_compatible import OpenAICompatibleProvider
from noris_ai.llm.schemas import ConversationTitleRequest
from tests.unit.test_conversation_titles import TitleProvider


@pytest.mark.parametrize("model_id", ["vllm/qsu/deepseek-v41-flash", "vllm/release/gpt-oss-120b"])
@pytest.mark.parametrize("limit,code", [(1024, None), (96, "OUTPUT_LIMIT")])
async def test_native_reasoning_title_with_total_completion_budget(
    llm_config: Settings,
    model_id: str,
    limit: int,
    code: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_provider_capabilities import payload

    requests: list[dict[str, object]] = []

    def reply(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=payload())
        body = json.loads(request.content)
        requests.append(body)
        # Reproduce reasoning exhausting the old 96-token limit without visible text.
        chunks: list[dict[str, object]] = [
            {"choices": [{"index": 0, "delta": {"reasoning_content": "private reasoning"}}]},
            {"choices": [{"index": 0, "delta": {"reasoning": "private reasoning"}}]},
        ]
        if body["max_tokens"] > 96:
            chunks.append({"choices": [{"index": 0, "delta": {"content": "Docker DNS-Probleme"}}]})
        chunks.append(
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "length" if code else "stop"}]}
        )
        data = (
            "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        )
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=data)

    config = llm_config.model_copy(update={"llm_title_max_output_tokens": limit})
    provider = OpenAICompatibleProvider(config, transport=httpx.MockTransport(reply))
    gateway = LLMGateway(config, provider)
    caplog.set_level(logging.INFO)
    request = ConversationTitleRequest(
        conversationId="native-title",
        inputMessageId="input",
        modelId=model_id,
        firstMessage="private source content",
    )
    try:
        if code:
            with pytest.raises(LLMError) as error:
                await gateway.conversation_title(request)
            assert error.value.code == code
        else:
            title = await gateway.conversation_title(request)
            assert title.title == "Docker DNS-Probleme"
        assert len(requests) == 1
        assert requests[0]["max_tokens"] == limit
        if model_id.endswith("gpt-oss-120b"):
            assert requests[0]["reasoning_effort"] == "low"
        else:
            assert "reasoning_effort" not in requests[0]
            assert "chat_template_kwargs" not in requests[0]
        assert "private reasoning" not in caplog.text
        assert "private source content" not in caplog.text
        assert "Docker DNS-Probleme" not in caplog.text
        assert "fixture-provider-key" not in caplog.text
    finally:
        await provider.aclose()


def lifecycle(
    config: Settings, provider: TitleProvider
) -> tuple[GenerationManager, AsyncMock, GenerateIncomingMessage, ChatMessage]:
    repository = AsyncMock(spec=ChatRepository)
    conversation_id, input_id = uuid4(), uuid4()
    command = GenerateIncomingMessage(
        version=1,
        type="chat.generate",
        requestId=uuid4(),
        conversationId=conversation_id,
        conversationVersion=1,
        inputMessageId=input_id,
        assistantMessageId=uuid4(),
        modelId="fixture-alpha",
        content="private source",
    )
    first = ChatMessage(
        id=input_id, conversation_id=conversation_id, role="user", content="private source"
    )
    repository.get_conversation.return_value = ChatConversation(
        id=conversation_id,
        title_source="fallback",
        title="Neuer Chat",
    )
    repository.claim_generated_title.return_value = True
    repository.set_generated_title.return_value = None
    manager = GenerationManager(
        config, cast(ChatRepository, repository), LLMGateway(config, provider)
    )
    return manager, repository, command, first


@pytest.mark.parametrize(
    "failure", ["INVALID_RESPONSE", "OUTPUT_LIMIT", "TIMEOUT", "BUDGET_LIMIT", "RATE_LIMIT"]
)
async def test_provider_failure_is_logged_without_retry_or_answer_mutation(
    llm_config: Settings,
    failure: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = TitleProvider(failure=failure)
    manager, repository, command, first = lifecycle(llm_config, provider)
    caplog.set_level(logging.INFO)
    await manager._generate_title(command, first)
    assert len(provider.calls) == 1
    repository.set_generated_title.assert_not_called()
    repository.persist_generation_event.assert_not_called()
    diagnostics = [
        json.loads(record.message) for record in caplog.records if record.message.startswith("{")
    ]
    failed = [record for record in diagnostics if record["outcome"] == "failure"]
    assert failed and all(record["error_code"] == failure for record in failed)
    assert all(record["conversation_id"] == str(command.conversationId) for record in diagnostics)
    assert all(
        record["model_id"] == command.modelId and record["duration_ms"] >= 0
        for record in diagnostics
    )
    assert "private source" not in caplog.text
    assert provider.output not in caplog.text


async def test_timeout_is_bounded_and_closes_provider(llm_config: Settings) -> None:
    provider = TitleProvider()
    provider.wait = True
    manager, repository, command, first = lifecycle(
        llm_config.model_copy(update={"llm_title_timeout_seconds": 0.01}), provider
    )
    await manager._generate_title(command, first)
    assert provider.closed.is_set()
    assert not manager.gateway._active
    repository.persist_generation_event.assert_not_called()


@pytest.mark.parametrize("failures", [1, 3])
async def test_database_write_retries_are_bounded_without_another_provider_call(
    llm_config: Settings,
    failures: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = TitleProvider()
    manager, repository, command, first = lifecycle(llm_config, provider)
    error = OperationalError("private sql", {}, Exception("private credentials"))
    repository.set_generated_title.side_effect = [error] * failures + [None]
    await manager._generate_title(command, first)
    assert repository.set_generated_title.await_count == (2 if failures == 1 else 3)
    assert len(provider.calls) == 1
    repository.persist_generation_event.assert_not_called()
    assert "private sql" not in caplog.text
    assert "private credentials" not in caplog.text


async def test_database_claim_failure_never_contacts_provider(llm_config: Settings) -> None:
    provider = TitleProvider()
    manager, repository, command, first = lifecycle(llm_config, provider)
    repository.claim_generated_title.side_effect = OperationalError(
        "private", {}, Exception("secret")
    )
    await manager._generate_title(command, first)
    assert not provider.calls
    assert not manager.gateway._active


@pytest.mark.parametrize(
    "source,claimed", [("manual", None), ("generated", None), ("fallback", True)]
)
async def test_existing_title_and_durable_claim_skip_before_admission(
    llm_config: Settings, source: str, claimed: bool | None
) -> None:
    provider = TitleProvider()
    manager, repository, command, first = lifecycle(llm_config, provider)
    repository.get_conversation.return_value.title_source = source
    repository.get_conversation.return_value.title_generation_claimed_at = claimed
    await manager._generate_title(command, first)
    assert not provider.calls
    repository.claim_generated_title.assert_not_called()


async def test_lost_claim_and_parallel_tasks_make_no_duplicate_calls(llm_config: Settings) -> None:
    provider = TitleProvider()
    manager, repository, command, first = lifecycle(llm_config, provider)
    provider.wait = True
    task = asyncio.create_task(manager._generate_title(command, first))
    await provider.received.wait()
    await manager._generate_title(command, first)
    assert len(provider.calls) == 1
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    repository.claim_generated_title.return_value = False
    await manager._generate_title(command, first)
    assert len(provider.calls) == 1


async def test_valid_title_after_transient_database_failure_is_broadcast_to_all_peers(
    llm_config: Settings,
) -> None:
    from datetime import UTC, datetime

    from noris_ai.chat.generation import Peer

    provider = TitleProvider()
    manager, repository, command, first = lifecycle(llm_config, provider)
    now = datetime.now(UTC)
    saved = ChatConversation(
        id=command.conversationId,
        owner_id=llm_config.chat_owner_id,
        title=provider.output,
        title_source="generated",
        version=2,
        created_at=now,
        updated_at=now,
    )
    repository.set_generated_title.side_effect = [
        OperationalError("private SQL", {}, Exception("private credentials")),
        saved,
    ]
    peers = [Peer(asyncio.Queue()), Peer(asyncio.Queue())]
    manager.peers.update(peers)
    await manager._generate_title(command, first)
    assert len(provider.calls) == 1
    assert repository.set_generated_title.await_count == 2
    for peer in peers:
        title, metadata = peer.queue.get_nowait(), peer.queue.get_nowait()
        assert title["type"] == "chat.title.updated"
        assert title["titleSource"] == "generated" and title["title"] == provider.output
        assert metadata["type"] == "chat.conversation.updated"
        assert cast(dict[str, object], metadata["conversation"])["version"] == 2


@pytest.mark.parametrize(
    "limit,code",
    [("llm_daily_token_budget", "BUDGET_LIMIT"), ("llm_requests_per_minute", "RATE_LIMIT")],
)
async def test_admission_failure_does_not_consume_durable_provider_claim(
    llm_config: Settings,
    limit: str,
    code: str,
) -> None:
    provider = TitleProvider()
    gateway = LLMGateway(llm_config.model_copy(update={limit: 0}), provider)
    claim = AsyncMock(return_value=True)
    request = ConversationTitleRequest(
        conversationId="admission",
        inputMessageId="input",
        modelId="fixture-alpha",
        firstMessage="Docker DNS",
    )
    with pytest.raises(LLMError) as error:
        await gateway.conversation_title(request, before_stream=claim)
    assert error.value.code == code
    claim.assert_not_called()
    assert not provider.calls
    # Only a subsequent explicit invocation can attempt admission again.
    gateway.config = llm_config
    await gateway.conversation_title(request, before_stream=claim)
    claim.assert_awaited_once()
    assert len(provider.calls) == 1
