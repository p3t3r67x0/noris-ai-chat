"""Regressions from the independent P7b adversarial review."""

# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from noris_ai.chat.models import ChatGeneration
from noris_ai.chat.repository import ModelDatabase
from noris_ai.core.config import Settings
from noris_ai.llm.gateway import LLMGateway
from noris_ai.research.grounding import GroundingContextBuilder, grounded_request
from noris_ai.research.planner import plan_research
from noris_ai.research.schemas import ResearchActivation
from noris_ai.tools.runtime import ToolRuntime
from tests.fixtures.tool_budget import MemoryTextBudget
from tests.unit.test_auto_continuation import Segments, worker
from tests.unit.test_llm_api import FixtureProvider
from tests.unit.test_research import fetched, request


@pytest.mark.parametrize(
    "question",
    [
        "Was gibt es Neues bei QGIS? Mein Kennwort ist fixture-only-abc.",
        "Was gibt es Neues bei QGIS? Mein API-Schlüssel lautet fixture-only-abc.",
        "Was gibt es Neues bei QGIS? Zugangsschlüssel ist sk-fixture-only-abc.",
        "Latest QGIS sk-proj-fixture-only-example",
        "Latest QGIS ghp_fixtureonlytoken",
        "Latest QGIS AKIAFIXTUREONLY123",
        "Latest QGIS -----BEGIN PRIVATE KEY-----",
    ],
)
def test_observable_credentials_never_reach_search(question: str):
    with pytest.raises(ValueError):
        plan_research(question, "de", datetime.now(UTC) + timedelta(seconds=60))


async def test_expired_deadline_never_opens_a_provider_request(llm_config: Settings):
    provider = FixtureProvider()
    gateway = LLMGateway(llm_config, provider)
    base = request()
    await gateway.reserve(base, input_token_reserve=2000)
    expired = grounded_request(base, [], []).model_copy(
        update={
            "research_deadline_at": datetime.now(UTC) - timedelta(seconds=1),
        }
    )
    events = [e async for e in gateway.events(expired)]
    assert any(e and e.type == "response.failed" and e.code == "TIMEOUT" for e in events)
    assert not provider.calls


async def test_cancel_after_text_reservation_commit_settles_possible_ledger(llm_config: Settings):
    class CommittedBudget(MemoryTextBudget):
        finishes = 0

        async def reserve_text(self, *args: object, **kwargs: object) -> None:
            self.phases[(llm_config.chat_owner_id, base.generationId)] = "reserved"
            raise asyncio.CancelledError

        async def finish_text(self, *args: object, **kwargs: object) -> None:
            self.finishes += 1
            self.phases[(llm_config.chat_owner_id, base.generationId)] = "released"

    base = request()
    budget = CommittedBudget(cast(ModelDatabase, object()))
    gateway = LLMGateway(llm_config, FixtureProvider(), budget)
    with pytest.raises(asyncio.CancelledError):
        await gateway.reserve(base, input_token_reserve=2000)
    await gateway.abandon(base.generationId)
    assert budget.finishes == 1
    assert budget.phases[(llm_config.chat_owner_id, base.generationId)] == "released"
    assert not gateway._active and not gateway._durable_phases


async def test_repeated_cancel_during_reservation_cleanup_drains_settlement(llm_config: Settings):
    finishing, release = asyncio.Event(), asyncio.Event()
    base = request()

    class InterruptedBudget(MemoryTextBudget):
        finishes = 0

        async def reserve_text(self, *args: object, **kwargs: object) -> None:
            self.phases[(llm_config.chat_owner_id, base.generationId)] = "reserved"
            raise asyncio.CancelledError

        async def finish_text(self, *args: object, **kwargs: object) -> None:
            self.finishes += 1
            finishing.set()
            await release.wait()
            self.phases[(llm_config.chat_owner_id, base.generationId)] = "released"

    budget = InterruptedBudget(cast(ModelDatabase, object()))
    gateway = LLMGateway(llm_config, FixtureProvider(), budget)
    task = asyncio.create_task(gateway.reserve(base, input_token_reserve=2000))
    await finishing.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await gateway.abandon(base.generationId)
    assert budget.finishes == 1
    assert budget.phases[(llm_config.chat_owner_id, base.generationId)] == "released"
    assert not gateway._active and not gateway._durable_phases


@pytest.mark.parametrize("title", [False, True])
async def test_cancel_during_stream_or_title_settlement_drains_ledger(
    llm_config: Settings, title: bool
):
    from noris_ai.llm.schemas import ConversationTitleRequest

    finishing, release = asyncio.Event(), asyncio.Event()
    base = request()

    class FinishingBudget(MemoryTextBudget):
        finishes = 0

        async def finish_text(self, owner: object, phase: str, *, unknown: bool = False) -> None:
            self.finishes += 1
            finishing.set()
            await release.wait()
            self.phases[(llm_config.chat_owner_id, phase)] = "accounted"

    budget = FinishingBudget(cast(ModelDatabase, object()))
    gateway = LLMGateway(llm_config, FixtureProvider(), budget)
    if title:

        async def title_call() -> None:
            await gateway.conversation_title(
                ConversationTitleRequest(
                    conversationId=base.conversationId,
                    inputMessageId=base.inputMessageId,
                    modelId=base.modelId,
                    firstMessage="Hallo",
                )
            )

        task = asyncio.create_task(title_call())
        phase = "title:" + base.conversationId
    else:
        await gateway.reserve(base)

        async def stream() -> None:
            async for _ in gateway.events(base):
                pass

        task = asyncio.create_task(stream())
        phase = base.generationId
    await finishing.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await gateway.abandon(phase)
    assert budget.finishes == 1 and budget.phases[(llm_config.chat_owner_id, phase)] == "accounted"
    assert not gateway._active and not gateway._durable_phases


async def test_partial_limitation_survives_context_omission(llm_config: Settings):
    gateway = LLMGateway(llm_config, FixtureProvider())
    base = request()
    model, capacity = await gateway.research_capacity(base)
    builder = GroundingContextBuilder(gateway)
    document = fetched()
    initial = builder.build(base, model, capacity, [document], partial_search=True)
    duplicate = fetched(document.document.text, "https://mirror.example.org/")
    tight = builder.build(
        base, model, initial.context_tokens, [document, duplicate], partial_search=True
    )
    assert len(tight.sources) == 1 and "partial_search_results" in tight.limitations
    assert tight.context_tokens <= initial.context_tokens


async def test_deadline_crossed_during_budget_dispatch_never_opens_provider(
    llm_config: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FixtureProvider()
    gateway = LLMGateway(llm_config, provider)
    base = request()
    await gateway.reserve(base, input_token_reserve=2000)
    future = grounded_request(base, [], []).model_copy(
        update={
            "research_deadline_at": datetime.now(UTC) + timedelta(milliseconds=20),
        }
    )

    async def dispatch(_: str) -> None:
        await asyncio.sleep(0.04)

    monkeypatch.setattr(gateway, "_dispatch_durable", dispatch)
    events = [e async for e in gateway.events(future)]
    assert any(e and e.type == "response.failed" and e.code == "TIMEOUT" for e in events)
    assert not provider.calls


async def test_stop_during_blocked_tool_cleanup_prevents_llm_start(
    llm_config: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    provider = Segments([("Should never be sent", None)])
    manager, live, base, snapshots = worker(llm_config, provider)
    prepared, release, stopping, cleanup = (asyncio.Event() for _ in range(4))
    live.research = ResearchActivation(llm_config.chat_owner_id, "de")

    async def prepare(*_: object):
        await manager.gateway.reserve(base, input_token_reserve=2000)
        prepared.set()
        await release.wait()
        return grounded_request(base, [], [])

    class Preparation:
        pass

    preparation = Preparation()
    monkeypatch.setattr(preparation, "prepare", prepare, raising=False)
    monkeypatch.setattr(manager, "research", preparation)

    class SlowTools:
        async def cancel(self, *_: object) -> None:
            stopping.set()
            await cleanup.wait()

    manager.tools = cast(ToolRuntime, SlowTools())

    async def generation(*_: object):
        return ChatGeneration(
            id=live.command.requestId,
            owner_id=llm_config.chat_owner_id,
            conversation_id=live.command.conversationId,
        )

    async def cancel(*_: object) -> None:
        pass

    monkeypatch.setattr(snapshots, "get_generation", generation, raising=False)
    monkeypatch.setattr(snapshots, "request_generation_cancel", cancel, raising=False)
    task = asyncio.create_task(manager._run(live, base, []))
    await prepared.wait()
    stopper = asyncio.create_task(manager.cancel(live.command.requestId))
    await stopping.wait()
    release.set()
    try:
        await asyncio.wait_for(task, 2)
        assert not provider.calls
        assert snapshots.events[-1]["type"] == "chat.generation.cancelled"
        assert live.cancellation_requested
    finally:
        cleanup.set()
        await stopper
