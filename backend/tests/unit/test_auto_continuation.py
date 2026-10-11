"""Exercise the persisted worker through the existing gateway, without a provider network."""

# pyright: reportPrivateUsage=false

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from noris_ai.chat.generation import GenerationManager, LiveGeneration, Peer
from noris_ai.chat.models import ChatConversation
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.core.config import EnvironmentSettings, Settings
from noris_ai.llm.errors import LLMError
from noris_ai.llm.gateway import LLMGateway
from noris_ai.llm.provider import ProviderMessage
from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import LLMMessage, LLMModel, PersistedChatRequest
from tests.fixtures.provider_catalog import provider_model


class Segments:
    def __init__(self, segments: Sequence[tuple[str, str | None]], *, quiet: bool = False) -> None:
        self.segments = segments
        self.calls: list[tuple[list[ProviderMessage], str]] = []
        self.closed = 0
        self.quiet = quiet
        self.continuing = asyncio.Event()

    async def discover_models(self) -> list[ProviderModel]:
        return [provider_model("fixture-alpha")]

    async def stream(
        self, messages: Sequence[ProviderMessage], model: LLMModel
    ) -> AsyncIterator[str]:
        index = len(self.calls)
        self.calls.append((list(messages), model.id))
        try:
            text, error = self.segments[index]
            for offset in range(0, len(text), 17):
                yield text[offset : offset + 17]
            if self.quiet and index == 1:
                self.continuing.set()
                await asyncio.Event().wait()
            if error:
                raise LLMError(error)
        finally:
            self.closed += 1

    async def aclose(self) -> None:
        pass


class Snapshots:
    def __init__(self, command: GenerateIncomingMessage) -> None:
        now = datetime.now(UTC)
        self.conversation = ChatConversation(
            id=command.conversationId,
            owner_id=UUID(int=1),
            title="Test",
            title_source="manual",
            created_at=now,
            updated_at=now,
            version=2,
            active_leaf_message_id=command.assistantMessageId,
        )
        self.events: list[dict[str, object]] = []
        self.contents: list[str] = []

    async def get_conversation(self, owner_id: UUID, conversation_id: UUID) -> ChatConversation:
        return self.conversation

    async def persist_generation_event(
        self,
        generation_id: UUID,
        payload: dict[str, object],
        content: str,
        status: str = "running",
        error_code: str | None = None,
    ) -> None:
        assert payload["seq"] == len(self.events) + 1
        self.events.append(payload)
        self.contents.append(content)


def worker(
    config: Settings, provider: Segments
) -> tuple[GenerationManager, LiveGeneration, PersistedChatRequest, Snapshots]:
    command = GenerateIncomingMessage(
        version=1,
        type="chat.generate",
        requestId=uuid4(),
        conversationId=uuid4(),
        inputMessageId=uuid4(),
        assistantMessageId=uuid4(),
        parentMessageId=uuid4(),  # Skip the independent first-message title request.
        conversationVersion=1,
        content="Frage",
        modelId="fixture-alpha",
    )
    request = PersistedChatRequest(
        generationId=str(command.requestId),
        conversationId=str(command.conversationId),
        inputMessageId=str(command.inputMessageId),
        modelId=command.modelId,
        messages=[LLMMessage(role="user", content=command.content)],
        attempt=1,
    )
    snapshots = Snapshots(command)
    manager = GenerationManager(
        config, cast(ChatRepository, snapshots), LLMGateway(config, provider)
    )
    live = LiveGeneration(command, peers={Peer(asyncio.Queue(maxsize=256))})
    manager.live[command.requestId] = live
    return manager, live, request, snapshots


@pytest.mark.parametrize("continuations", [0, 1, 3, 8])
async def test_length_chains_until_stop_on_one_node(
    llm_config: Settings, continuations: int
) -> None:
    parts = [(f"Teil {i}. ", "OUTPUT_LIMIT") for i in range(continuations)] + [("Ende.", None)]
    provider = Segments(parts)
    manager, live, request, snapshots = worker(llm_config, provider)
    await manager._run(live, request, [])
    events = snapshots.events
    assert events[-1]["type"] == "chat.generation.completed"
    assert events[-1]["content"] == "".join(part for part, _ in parts)
    assert events[-1]["continuationCount"] == continuations
    assert sum(e["type"] == "chat.generation.started" for e in events) == 1
    assert all(
        e["type"] in ("chat.generation.started", "chat.generation.delta") for e in events[:-1]
    )
    assert all(e["messageId"] == str(live.command.assistantMessageId) for e in events)
    assert all(e["generationId"] == request.generationId for e in events)
    assert provider.closed == len(provider.calls) == continuations + 1
    assert all(model == request.modelId for _, model in provider.calls)
    for index, (messages, _) in enumerate(provider.calls[1:], start=1):
        assert messages[0].role == "system"
        assert messages[-2].content == "".join(part for part, _ in parts[:index])
    assert not manager.gateway._active


@pytest.mark.parametrize(
    "automatic,total,count,code",
    [
        (0, 8, 0, "AUTO_CONTINUATION_LIMIT"),
        (2, 8, 2, "AUTO_CONTINUATION_LIMIT"),
        (8, 2, 2, "CONTINUATION_LIMIT"),
    ],
)
async def test_both_continuation_caps_preserve_text(
    llm_config: Settings, automatic: int, total: int, count: int, code: str
) -> None:
    config = llm_config.model_copy(
        update={"chat_auto_continue_max": automatic, "llm_max_continuations": total}
    )
    provider = Segments([("Neuer Text. ", "OUTPUT_LIMIT")] * 4)
    manager, live, request, snapshots = worker(config, provider)
    await manager._run(live, request, [])
    assert len(provider.calls) == count + 1
    assert snapshots.events[-1]["type"] == "chat.generation.incomplete"
    assert snapshots.events[-1]["code"] == code
    assert snapshots.events[-1]["content"] == "Neuer Text. " * (count + 1)
    assert snapshots.events[-1]["continuationCount"] == count


@pytest.mark.parametrize(
    "code", ["RATE_LIMIT", "CONTEXT_LIMIT", "PROVIDER_ERROR", "CONTENT_FILTERED", "TIMEOUT"]
)
async def test_continuation_errors_end_once_and_keep_partial_text(
    llm_config: Settings, code: str
) -> None:
    provider = Segments([("Anfang. ", "OUTPUT_LIMIT"), ("Neue Wörter. ", code)])
    manager, live, request, snapshots = worker(llm_config, provider)
    await manager._run(live, request, [])
    assert len(provider.calls) == 2
    assert snapshots.events[-1]["type"] == "chat.generation.failed"
    assert snapshots.events[-1]["code"] == code
    assert snapshots.events[-1]["content"] == "Anfang. Neue Wörter. "


@pytest.mark.parametrize(
    "limits,part,code",
    [
        ({"llm_daily_token_budget": 2000}, "Anfang. ", "BUDGET_LIMIT"),
        ({"llm_requests_per_minute": 1}, "Anfang. ", "RATE_LIMIT"),
        ({}, "a" * 7000, "CONTEXT_LIMIT"),
        ({"llm_max_response_chars": 100}, "a" * 100, "RESPONSE_SIZE_LIMIT"),
    ],
)
async def test_every_call_checks_admission(
    llm_config: Settings, limits: dict[str, int], part: str, code: str
) -> None:
    provider = Segments([(part, "OUTPUT_LIMIT"), ("Forbidden", None)])
    manager, live, request, snapshots = worker(llm_config.model_copy(update=limits), provider)
    await manager._run(live, request, [])
    assert len(provider.calls) == 1
    assert snapshots.events[-1]["type"] == "chat.generation.failed"
    assert snapshots.events[-1]["code"] == code
    assert snapshots.events[-1]["content"] == part
    assert snapshots.events[-1]["continuationCount"] == 0
    assert not manager.gateway._active


@pytest.mark.parametrize(
    "first,second",
    [
        ("", ""),
        (" \n", ""),
        ("Existing sentence. " * 10, ""),
        ("Existing sentence. " * 10, " \n"),
        ("Existing sentence. " * 10, "Existing sentence. " * 10),
    ],
)
async def test_no_progress_stops_without_another_call(
    llm_config: Settings, first: str, second: str
) -> None:
    provider = Segments([(first, "OUTPUT_LIMIT"), (second, "OUTPUT_LIMIT"), ("Forbidden", None)])
    manager, live, request, snapshots = worker(llm_config, provider)
    await manager._run(live, request, [])
    assert len(provider.calls) == (2 if first.strip() else 1)
    assert snapshots.events[-1]["type"] == "chat.generation.failed"
    assert snapshots.events[-1]["code"] == "DUPLICATE_CONTINUATION"
    assert str(snapshots.events[-1]["content"]).startswith(first)


async def test_overlap_and_open_markdown_are_preserved(llm_config: Settings) -> None:
    first = "# Antwort\n\n```python\n" + "print('alt')\n" * 10
    new = "print('neu')\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- Punkt\n"
    provider = Segments([(first, "OUTPUT_LIMIT"), (first[-80:] + new, None)])
    manager, live, request, snapshots = worker(llm_config, provider)
    await manager._run(live, request, [])
    assert snapshots.events[-1]["content"] == first + new
    streamed = "".join(
        str(e["delta"]) for e in snapshots.events if e["type"] == "chat.generation.delta"
    )
    assert streamed == first + new


async def test_stop_during_quiet_continuation_closes_provider(llm_config: Settings) -> None:
    provider = Segments([("Anfang. ", "OUTPUT_LIMIT"), ("Neue Wörter. ", None)], quiet=True)
    manager, live, request, snapshots = worker(llm_config, provider)
    task = asyncio.create_task(manager._run(live, request, []))
    await asyncio.wait_for(provider.continuing.wait(), 2)
    live.cancellation_requested = True
    await asyncio.wait_for(task, 2)
    assert provider.closed == len(provider.calls) == 2
    assert snapshots.events[-1]["type"] == "chat.generation.cancelled"
    assert snapshots.events[-1]["content"] == "Anfang. Neue Wörter. "
    assert snapshots.events[-1]["continuationCount"] == 1
    assert not manager.gateway._active


def test_auto_continue_setting_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NORIS_CHAT_AUTO_CONTINUE_MAX", "3")
    assert EnvironmentSettings().chat_auto_continue_max == 3
    for value in ("-1", "21"):
        monkeypatch.setenv("NORIS_CHAT_AUTO_CONTINUE_MAX", value)
        with pytest.raises(ValidationError):
            EnvironmentSettings()
