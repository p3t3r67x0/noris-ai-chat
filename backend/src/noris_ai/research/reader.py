"""Public evidence read from existing generation/ToolResult persistence only."""

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatGeneration, ChatMessage
from noris_ai.llm.errors import LLMError
from noris_ai.research.grounding import assess_answer
from noris_ai.research.schemas import ResearchProjection, ResearchSource, ResearchView
from noris_ai.tools.errors import ToolError
from noris_ai.tools.models import ToolRun
from noris_ai.tools.registry import canonical_payload, payload_digest
from noris_ai.tools.repository import ToolRepository
from noris_ai.tools.schemas import FetchInput, SearchResult, SourceDocument


async def read_research(
    session: AsyncSession,
    tools: ToolRepository,
    owner: UUID,
    conversation: UUID,
    generation_id: UUID,
) -> ResearchView | None:
    """Fail closed on ambiguous ancestry, scopes, documents or citation offsets.

    Explicit continuations inherit only citations inside the unchanged copied
    prefix. Newly generated continuation text has no grounding assessment and
    never receives inherited citation authority. Regeneration/edit have no chain.
    """
    visible = await session.scalar(
        select(ChatConversation.id).where(
            ChatConversation.id == conversation,
            ChatConversation.owner_id == owner,
            ChatConversation.deleted_at.is_(None),
        )
    )
    if visible is None:
        raise ChatError("NOT_FOUND", 404)
    generation = await session.scalar(
        select(ChatGeneration).where(
            ChatGeneration.id == generation_id,
            ChatGeneration.owner_id == owner,
            ChatGeneration.conversation_id == conversation,
        )
    )
    if generation is None:
        raise ChatError("GENERATION_NOT_FOUND", 404)
    message = await session.get(ChatMessage, generation.assistant_message_id)
    if (
        message is None
        or message.conversation_id != conversation
        or message.role != "assistant"
        or message.generation_id != generation.id
    ):
        raise ChatError("NOT_FOUND", 404)
    original = generation
    citation_text = message.content
    seen: set[UUID] = set()
    for _ in range(21):
        if generation.id in seen:
            raise ChatError("INVALID_INPUT", 422)
        seen.add(generation.id)
        if generation.research is not None:
            break
        if generation.operation != "continue" or generation.source_message_id is None:
            return None
        source = await session.scalar(
            select(ChatMessage).where(
                ChatMessage.id == generation.source_message_id,
                ChatMessage.conversation_id == conversation,
                ChatMessage.role == "assistant",
            )
        )
        if source is None or not citation_text.startswith(source.content):
            raise ChatError("INVALID_INPUT", 422)
        generation = await session.scalar(
            select(ChatGeneration).where(
                ChatGeneration.id == source.generation_id,
                ChatGeneration.owner_id == owner,
                ChatGeneration.conversation_id == conversation,
                ChatGeneration.assistant_message_id == source.id,
            )
        )
        if generation is None:
            raise ChatError("INVALID_INPUT", 422)
        citation_text = source.content
    else:
        raise ChatError("INVALID_INPUT", 422)
    try:
        projection = ResearchProjection.model_validate_json(json.dumps(generation.research))
        if projection.generation_id != generation.id:
            raise ValueError("Invalid scope")
        sources: list[ResearchSource] = []
        if len({s.marker for s in projection.sources}) != len(projection.sources):
            raise ValueError("Duplicate markers")
        for evidence in projection.sources:
            search = await tools.research_snapshot(
                session, owner, conversation, generation.id, evidence.search_run_id, "web.search.v1"
            )
            document = await tools.research_snapshot(
                session, owner, conversation, generation.id, evidence.fetch_run_id, "web.fetch.v1"
            )
            fetch = await session.get(ToolRun, evidence.fetch_run_id)
            if not isinstance(search, SearchResult) or not isinstance(document, SourceDocument):
                raise ValueError("Invalid document")
            matches = [s for s in search.sources if s.source_id == evidence.source_id]
            if (
                len(matches) != 1
                or fetch is None
                or fetch.source_search_run_id != evidence.search_run_id
                or document.source_id != evidence.source_id
                or document.digest != evidence.content_digest
                or document.final_url != evidence.final_url
                or document.fetched_at != evidence.fetched_at
                or matches[0].url != evidence.original_url
                or matches[0].title != evidence.title
                or evidence.excerpt_end > len(document.text)
                or evidence.excerpt != document.text[evidence.excerpt_start : evidence.excerpt_end]
            ):
                raise ValueError("Invalid provenance")
            sources.append(
                ResearchSource(
                    marker=evidence.marker,
                    sourceId=evidence.source_id,
                    searchRunId=evidence.search_run_id,
                    fetchRunId=evidence.fetch_run_id,
                    title=evidence.title,
                    originalUrl=evidence.original_url,
                    finalUrl=evidence.final_url,
                    fetchedAt=evidence.fetched_at,
                    status="context_prepared",
                    excerpt=evidence.excerpt,
                    contentDigest=evidence.content_digest,
                )
            )
        for missing in projection.unavailable:
            search = await tools.research_snapshot(
                session, owner, conversation, generation.id, missing.search_run_id, "web.search.v1"
            )
            fetch = await session.scalar(
                select(ToolRun).where(
                    ToolRun.id == missing.fetch_run_id,
                    ToolRun.owner_id == owner,
                    ToolRun.conversation_id == conversation,
                    ToolRun.generation_id == generation.id,
                    ToolRun.source_search_run_id == missing.search_run_id,
                    ToolRun.tool_id == "web.fetch.v1",
                    ToolRun.state.in_(("failed", "timed_out")),
                    ToolRun.parent_run_id.is_(None),
                )
            )
            if not isinstance(search, SearchResult) or fetch is None:
                raise ValueError("Invalid unavailable source")
            matches = [s for s in search.sources if s.source_id == missing.source_id]
            value = FetchInput.model_validate_json(json.dumps(fetch.input))
            if (
                len(matches) != 1
                or value.source_id != missing.source_id
                or payload_digest(canonical_payload(value)) != fetch.input_digest
            ):
                raise ValueError("Invalid unavailable input")
            sources.append(
                ResearchSource(
                    sourceId=missing.source_id,
                    searchRunId=missing.search_run_id,
                    fetchRunId=missing.fetch_run_id,
                    title=matches[0].title,
                    originalUrl=matches[0].url,
                    status="unavailable",
                )
            )
        # Observe only a persisted answer. Streaming markers are never provisional links.
        assessment = (
            assess_answer(citation_text, projection.sources) if projection.assessment else None
        )
        return ResearchView(
            generationId=original.id,
            sourceGenerationId=generation.id,
            state=projection.state,
            inherited=original.id != generation.id,
            modelResponseObserved=projection.model_response_observed,
            sources=sources,
            citations=assessment.citations if assessment else [],
        )
    except (ValueError, TypeError, ToolError):
        raise LLMError("RESEARCH_FAILED", 422) from None
