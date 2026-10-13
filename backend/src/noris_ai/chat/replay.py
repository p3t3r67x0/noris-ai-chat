"""Consistent, bounded replay of the existing chat outbox and durable snapshots."""

import json
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatGeneration, ChatMessage, ChatStreamEvent
from noris_ai.chat.repository import ModelDatabase, utc_now
from noris_ai.tools.events import (
    MAX_GENERATION_TOOL_RUNS,
    TOOL_SNAPSHOT_PAGE_SIZE,
    ToolEvent,
    ToolSnapshotEvent,
)
from noris_ai.tools.models import ToolRun

if TYPE_CHECKING:
    from noris_ai.tools.repository import ToolRepository


async def replay(
    database: ModelDatabase,
    owner: UUID,
    generation_id: UUID,
    after: int,
    capacity: int,
    tools: "ToolRepository | None",
    *,
    include_tools: bool,
    initial: bool,
) -> tuple[list[dict[str, object]], int]:
    async with database() as session, session.begin():
        scope = await session.scalar(
            select(ChatGeneration).where(
                ChatGeneration.id == generation_id,
                ChatGeneration.owner_id == owner,
            )
        )
        if scope is None:
            raise ChatError("GENERATION_NOT_FOUND", 404)
        conversation = await session.scalar(
            select(ChatConversation)
            .where(
                ChatConversation.id == scope.conversation_id,
                ChatConversation.owner_id == owner,
                ChatConversation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if conversation is None:
            raise ChatError("NOT_FOUND", 404)
        generation = await session.scalar(
            select(ChatGeneration)
            .where(
                ChatGeneration.id == generation_id,
                ChatGeneration.owner_id == owner,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if generation is None:
            raise ChatError("GENERATION_NOT_FOUND", 404)
        if after > generation.last_sequence:
            raise ChatError("INVALID_INPUT", 422)
        rows = list(
            await session.scalars(
                select(ChatStreamEvent)
                .where(
                    ChatStreamEvent.generation_id == generation_id,
                    ChatStreamEvent.sequence > after,
                )
                .order_by(ChatStreamEvent.sequence)
                .limit(capacity + 1)
            )
        )
        contiguous = (
            bool(rows)
            and rows[-1].sequence == generation.last_sequence
            and all(row.sequence == after + i + 1 for i, row in enumerate(rows))
        )
        snapshot = (
            not contiguous
            or (
                generation.status == "interrupted"
                and not any(row.event_type == "chat.generation.interrupted" for row in rows)
            )
            or len(rows) > capacity
            or (initial and generation.operation == "continue")
            or (not include_tools and any(row.event_type.startswith("tool.") for row in rows))
        )
        events: list[dict[str, object]] = []
        # Send tool snapshots BEFORE a replayed terminal chat event: the stream
        # consumer may finish immediately on that terminal event.
        if include_tools and tools is not None and (initial or snapshot):
            runs = list(
                await session.scalars(
                    select(ToolRun)
                    .where(
                        ToolRun.owner_id == owner,
                        ToolRun.conversation_id == generation.conversation_id,
                        ToolRun.generation_id == generation_id,
                    )
                    .order_by(ToolRun.created_at, ToolRun.id)
                    .limit(MAX_GENERATION_TOOL_RUNS + 1)
                )
            )
            if len(runs) > MAX_GENERATION_TOOL_RUNS:
                raise ChatError("INVALID_INPUT", 422)
            projections = [await tools.projection(session, run) for run in runs]
            for offset in range(0, max(1, len(projections)), TOOL_SNAPSHOT_PAGE_SIZE):
                events.append(
                    ToolSnapshotEvent(
                        conversationId=generation.conversation_id,
                        generationId=generation_id,
                        lastSequence=generation.last_sequence,
                        timestamp=utc_now(),
                        runs=projections[offset : offset + TOOL_SNAPSHOT_PAGE_SIZE],
                    ).model_dump(mode="json")
                )
        if len(events) + len(rows) > capacity:
            snapshot = True
        if snapshot:
            message = await session.get(ChatMessage, generation.assistant_message_id)
            if message is None:
                raise ChatError("NOT_FOUND", 404)
            events.append(
                {
                    "version": 1,
                    "type": "chat.resume.snapshot",
                    "generationId": str(generation_id),
                    "conversationId": str(generation.conversation_id),
                    "messageId": str(message.id),
                    "status": generation.status,
                    "content": message.content,
                    "lastSequence": generation.last_sequence,
                    "continuationCount": message.continuation_count,
                    "code": message.error_code,
                    "message": message.error_message,
                }
            )
        else:
            permitted_runs = (
                set(
                    await session.scalars(
                        select(ToolRun.id).where(
                            ToolRun.owner_id == owner,
                            ToolRun.conversation_id == generation.conversation_id,
                            ToolRun.generation_id == generation_id,
                        )
                    )
                )
                if include_tools
                else set[UUID]()
            )
            for row in rows:
                payload = row.payload
                if row.event_type.startswith("tool."):
                    event = ToolEvent.model_validate_json(json.dumps(payload))
                    if (
                        event.generationId != generation_id
                        or event.runId not in permitted_runs
                        or event.conversationId != generation.conversation_id
                        or event.seq != row.sequence
                    ):
                        raise ChatError("INVALID_INPUT", 422)
                    payload = event.model_dump(mode="json")
                events.append(payload)
        return events, generation.last_sequence
