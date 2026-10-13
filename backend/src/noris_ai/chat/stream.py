"""One transactional sequence allocator for chat and tool events.

Callers hold the conversation and generation row locks, in that order.
The existing chat_stream_event table is the durable outbox.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.models import ChatGeneration, ChatStreamEvent


def append_event(
    session: AsyncSession, generation: ChatGeneration, payload: dict[str, object]
) -> int:
    generation.last_sequence += 1
    payload["seq"] = generation.last_sequence
    session.add(
        ChatStreamEvent(
            generation_id=generation.id,
            sequence=generation.last_sequence,
            event_type=str(payload["type"]),
            payload=payload,
        )
    )
    return generation.last_sequence
