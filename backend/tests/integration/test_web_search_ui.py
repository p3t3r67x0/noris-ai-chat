"""Public P7c intent and readers on existing disposable PostgreSQL fixtures."""

import asyncio
import json
from uuid import UUID, uuid4

import pytest

from noris_ai.chat.errors import ChatError
from noris_ai.chat.generation import GenerationManager, Peer
from noris_ai.chat.models import ChatGeneration, ChatMessage
from noris_ai.chat.replay import replay
from noris_ai.chat.ws_protocol import GenerateIncomingMessage
from noris_ai.llm.errors import LLMError
from noris_ai.research.reader import read_research
from noris_ai.research.schemas import ResearchIntent, ResearchProjection
from tests.integration import test_research_runtime as p7b

pytestmark = pytest.mark.integration
tool_schema = p7b.tool_schema
tools = p7b.tools
fetch = p7b.fetch
research = p7b.research


async def view(fixture: p7b.ResearchFixture, generation: UUID | None = None):
    async with fixture.chat.database() as session:
        return await read_research(
            session,
            fixture.base.runtime.repository,
            fixture.activation.owner_id,
            fixture.base.base.conversation,
            generation or fixture.base.base.generation,
        )


async def finish(fixture: p7b.ResearchFixture):
    await fixture.prepare()
    await fixture.chat.persist_generation_event(
        fixture.base.base.generation,
        {
            "version": 1,
            "type": "chat.generation.incomplete",
            "seq": 1,
            "generationId": str(fixture.base.base.generation),
            "conversationId": str(fixture.base.base.conversation),
            "messageId": str(fixture.assistant),
            "content": "🌍 Claim [[R1]]. Unknown [[R9]].",
            "reason": "output_limit",
        },
        "🌍 Claim [[R1]]. Unknown [[R9]].",
        "incomplete",
    )


async def test_authorized_reader_revalidates_sources_and_exact_unicode_citations(
    research: p7b.ResearchFixture,
):
    await finish(research)
    result = await view(research)
    assert result is not None
    assert len(result.sources) == 1 and result.sources[0].status == "context_prepared"
    assert [citation.marker for citation in result.citations] == ["R1"]
    assert result.citations[0].start == 8
    assert result.claimSupport == "unverified"
    async with research.chat.database() as session:
        with pytest.raises(ChatError):
            await read_research(
                session,
                research.base.runtime.repository,
                uuid4(),
                research.base.base.conversation,
                research.base.base.generation,
            )
        with pytest.raises(ChatError):
            await read_research(
                session,
                research.base.runtime.repository,
                research.activation.owner_id,
                uuid4(),
                research.base.base.generation,
            )


@pytest.mark.parametrize(
    "field",
    ["source_id", "search_run_id", "fetch_run_id", "excerpt", "original_url", "content_digest"],
)
async def test_reader_fails_closed_for_tampered_provenance(
    research: p7b.ResearchFixture, field: str
):
    await finish(research)
    async with research.chat.database() as session, session.begin():
        generation = await session.get(ChatGeneration, research.base.base.generation)
        assert generation is not None and generation.research is not None
        payload = json.loads(json.dumps(generation.research))
        payload["sources"][0][field] = (
            "fake source"
            if field == "excerpt"
            else "https://forged.example.org/"
            if field == "original_url"
            else "0" * 64
            if field == "content_digest"
            else str(uuid4())
        )
        generation.research = payload
    with pytest.raises(LLMError, match="Recherche"):
        await view(research)


async def test_explicit_continuation_attributes_only_unchanged_copied_prefix(
    research: p7b.ResearchFixture,
):
    await finish(research)
    original = await view(research)
    assert original is not None
    saved = await research.chat.get_generation(
        research.activation.owner_id, research.base.base.generation
    )
    command = GenerateIncomingMessage(
        version=1,
        type="chat.generate",
        requestId=uuid4(),
        conversationId=research.base.base.conversation,
        inputMessageId=saved.input_message_id,
        assistantMessageId=uuid4(),
        modelId=saved.model_id,
        operation="continue",
        sourceAssistantMessageId=research.assistant,
        content=research.request.messages[0].content,
        conversationVersion=(
            await research.chat.get_conversation(
                research.activation.owner_id, research.base.base.conversation
            )
        ).version,
    )
    generation, _, _ = await research.chat.begin_generation(research.activation.owner_id, command)
    content = "🌍 Claim [[R1]]. Unknown [[R9]]. New ungrounded claim [[R1]]."
    await research.chat.persist_generation_event(
        generation.id,
        {"version": 1, "type": "chat.generation.completed", "seq": 1, "content": content},
        content,
        "completed",
    )
    inherited = await view(research, generation.id)
    assert inherited is not None and inherited.inherited
    assert inherited.generationId == generation.id and inherited.sourceGenerationId == saved.id
    assert inherited.citations == original.citations
    assert len(inherited.sources) == 1
    async with research.chat.database() as session:
        message = await session.get(ChatMessage, command.assistantMessageId)
        assert message is not None
        # Database immutability also rejects this write. Exercise the reader's
        # defensive prefix check against a corrupt in-memory identity snapshot.
        with session.no_autoflush:
            message.content = "Altered prefix [[R1]]"
            with pytest.raises(ChatError):
                await read_research(
                    session,
                    research.base.runtime.repository,
                    research.activation.owner_id,
                    research.base.base.conversation,
                    generation.id,
                )


async def test_public_intent_persists_denial_and_old_clients_resume_compatibly(
    research: p7b.ResearchFixture,
):
    await research.chat.mark_running_generations_interrupted(research.activation.owner_id)
    config = research.service.config.model_copy(update={"research_enabled": False})
    manager = GenerationManager(
        config, research.chat, research.gateway, tools=research.base.runtime
    )
    peer = Peer(asyncio.Queue(maxsize=64))
    command = GenerateIncomingMessage(
        version=1,
        type="chat.generate",
        researchEventVersion=1,
        research=ResearchIntent(version=1, mode="web", language="en"),
        requestId=uuid4(),
        conversationId=research.base.base.conversation,
        inputMessageId=uuid4(),
        assistantMessageId=uuid4(),
        modelId="fixture-beta",
        parentMessageId=research.assistant,
        content="What is QGIS?",
        conversationVersion=(
            await research.chat.get_conversation(
                research.activation.owner_id, research.base.base.conversation
            )
        ).version,
    )
    await manager.generate(peer, command)
    await asyncio.gather(*manager.tasks)
    generation = await research.chat.get_generation(research.activation.owner_id, command.requestId)
    assert generation.status == "failed" and generation.error_code == "RESEARCH_DISABLED"
    assert generation.research is not None
    stored = ResearchProjection.model_validate_json(json.dumps(generation.research))
    assert stored.intent is not None and stored.intent.mode == "web"
    result = await view(research, command.requestId)
    assert result is not None and result.state == "failed" and not result.sources
    old, _ = await replay(
        research.chat.database,
        research.activation.owner_id,
        command.requestId,
        0,
        64,
        research.base.runtime.repository,
        include_tools=False,
        initial=True,
    )
    assert [event["type"] for event in old] == ["chat.resume.snapshot"]
    compatible, _ = await replay(
        research.chat.database,
        research.activation.owner_id,
        command.requestId,
        0,
        64,
        research.base.runtime.repository,
        include_tools=True,
        include_research=True,
        initial=True,
    )
    assert any(event["type"] == "research.updated" for event in compatible)
    before = generation.last_sequence
    # Exact retry resumes; changing intent on the same Request-ID is rejected.
    await manager.generate(peer, command)
    assert (
        await research.chat.get_generation(research.activation.owner_id, command.requestId)
    ).last_sequence == before
    with pytest.raises(ChatError):
        await manager.generate(peer, command.model_copy(update={"research": None}))
