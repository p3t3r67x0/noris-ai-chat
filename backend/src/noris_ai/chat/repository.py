"""SQLAlchemy repository for chat persistence.

Every query is scoped to the server-side owner; clients can never supply or
override ownership. The message tree is append-only: edits and regenerations
create siblings instead of overwriting messages.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import (
    ChatConversation,
    ChatDraft,
    ChatGeneration,
    ChatMessage,
    ChatStreamEvent,
    ChatUserPreferences,
)
from noris_ai.chat.schemas import MessageStatus, TitleSource

ModelDatabase = async_sessionmaker[AsyncSession]
UNCHANGED = object()


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChatRepository:
    def __init__(self, database: ModelDatabase) -> None:
        self._database = database

    # --- conversations -------------------------------------------------

    async def list_conversations(
        self, owner_id: uuid.UUID, *, include_archived: bool
    ) -> Sequence[ChatConversation]:
        query = (
            select(ChatConversation)
            .where(
                ChatConversation.owner_id == owner_id,
                ChatConversation.deleted_at.is_(None),
            )
            .order_by(desc(ChatConversation.updated_at))
        )
        if not include_archived:
            query = query.where(ChatConversation.archived_at.is_(None))
        async with self._database() as session:
            return (await session.scalars(query)).all()

    async def get_conversation(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> ChatConversation:
        async with self._database() as session:
            conversation = await session.get(ChatConversation, conversation_id)
        if (
            conversation is None
            or conversation.owner_id != owner_id
            or conversation.deleted_at is not None
        ):
            raise ChatError("NOT_FOUND", 404)
        return conversation

    async def create_conversation(
        self,
        owner_id: uuid.UUID,
        *,
        title: str,
        title_source: TitleSource = "fallback",
        conversation_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        active_leaf_message_id: uuid.UUID | None = None,
    ) -> ChatConversation:
        created_id = conversation_id if conversation_id is not None else uuid.uuid4()
        values: dict[str, object] = {
            "id": created_id,
            "owner_id": owner_id,
            "title": title,
            "title_source": title_source,
            "active_leaf_message_id": active_leaf_message_id,
        }
        if created_at is not None:
            values["created_at"] = created_at
        async with self._database() as session:
            await session.execute(insert(ChatConversation).values(values))
            await session.commit()
            conversation = await session.get(ChatConversation, created_id)
            if conversation is None:  # pragma: no cover - insert just succeeded
                raise ChatError("INTERNAL_ERROR", 500)
            return conversation

    async def update_conversation(
        self,
        owner_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        expected_version: int,
        title: str | None = None,
        title_source: TitleSource | None = None,
        archived: bool | None = None,
        active_leaf_message_id: object | uuid.UUID | None = UNCHANGED,
        bump_last_message: bool = False,
    ) -> ChatConversation:
        """Optimistic-lock update; returns the refreshed conversation."""
        async with self._database() as session:
            conversation = await session.get(ChatConversation, conversation_id)
            if (
                conversation is None
                or conversation.owner_id != owner_id
                or conversation.deleted_at is not None
            ):
                raise ChatError("NOT_FOUND", 404)
            if conversation.version != expected_version:
                raise ChatError("VERSION_CONFLICT", 409)
            if title is not None:
                conversation.title = title
                if title_source is not None:
                    conversation.title_source = title_source
            if archived is not None:
                conversation.archived_at = utc_now() if archived else None
            if active_leaf_message_id is not UNCHANGED:
                conversation.active_leaf_message_id = active_leaf_message_id  # type: ignore[assignment]
            conversation.version += 1
            conversation.updated_at = utc_now()
            if bump_last_message:
                conversation.last_message_at = utc_now()
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def set_generated_title(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID, title: str
    ) -> ChatConversation | None:
        """Generated titles never overwrite manual titles."""
        async with self._database() as session:
            conversation = await session.get(ChatConversation, conversation_id)
            if (
                conversation is None
                or conversation.owner_id != owner_id
                or conversation.deleted_at is not None
            ):
                return None
            if conversation.title_source == "manual":
                return conversation
            conversation.title = title
            conversation.title_source = "generated"
            conversation.version += 1
            conversation.updated_at = utc_now()
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def soft_delete_conversation(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        async with self._database() as session:
            conversation = await session.get(ChatConversation, conversation_id)
            if (
                conversation is None
                or conversation.owner_id != owner_id
                or conversation.deleted_at is not None
            ):
                raise ChatError("NOT_FOUND", 404)
            conversation.deleted_at = utc_now()
            await session.commit()

    # --- messages ------------------------------------------------------

    async def list_messages(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Sequence[ChatMessage]:
        await self.get_conversation(owner_id, conversation_id)
        query = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        async with self._database() as session:
            return (await session.scalars(query)).all()

    async def get_message(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> ChatMessage:
        await self.get_conversation(owner_id, conversation_id)
        async with self._database() as session:
            message = await session.get(ChatMessage, message_id)
        if message is None or message.conversation_id != conversation_id:
            raise ChatError("NOT_FOUND", 404)
        return message

    async def append_user_message(
        self,
        owner_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        message_id: uuid.UUID,
        parent_message_id: uuid.UUID | None,
        content: str,
        edited_from_message_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
    ) -> ChatMessage:
        """Idempotent insert: an existing identical message is returned."""
        await self.get_conversation(owner_id, conversation_id)
        if parent_message_id is not None:
            parent = await self.get_message(owner_id, conversation_id, parent_message_id)
            if parent.role != "assistant":
                raise ChatError("INVALID_PARENT", 422)
        values: dict[str, object] = {
            "id": message_id,
            "conversation_id": conversation_id,
            "parent_message_id": parent_message_id,
            "role": "user",
            "content": content,
            "status": "completed",
            "edited_from_message_id": edited_from_message_id,
        }
        if created_at is not None:
            values["created_at"] = created_at
            values["updated_at"] = created_at
        async with self._database() as session:
            existing = await session.get(ChatMessage, message_id)
            if existing is not None:
                if (
                    existing.conversation_id != conversation_id
                    or existing.role != "user"
                    or existing.content != content
                    or existing.parent_message_id != parent_message_id
                ):
                    raise ChatError("MESSAGE_EXISTS", 409)
                return existing
            await session.execute(insert(ChatMessage).values(values))
            message = await session.get(ChatMessage, message_id)
            if message is None:  # pragma: no cover - insert just succeeded
                raise ChatError("INTERNAL_ERROR", 500)
            await session.commit()
            return message

    async def append_message(self, message: ChatMessage) -> ChatMessage:
        """Import path: insert a fully specified message row."""
        async with self._database() as session:
            await session.execute(
                insert(ChatMessage).values(
                    {
                        "id": message.id,
                        "conversation_id": message.conversation_id,
                        "parent_message_id": message.parent_message_id,
                        "role": message.role,
                        "content": message.content,
                        "model_id": message.model_id,
                        "status": message.status,
                        "generation_id": message.generation_id,
                        "edited_from_message_id": message.edited_from_message_id,
                        "created_at": message.created_at,
                        "updated_at": message.updated_at,
                    }
                )
            )
            await session.commit()
            inserted = await session.get(ChatMessage, message.id)
            if inserted is None:  # pragma: no cover - insert just succeeded
                raise ChatError("INTERNAL_ERROR", 500)
            return inserted

    async def update_assistant_message(
        self,
        message_id: uuid.UUID,
        *,
        content: str | None = None,
        status: MessageStatus | None = None,
    ) -> None:
        values: dict[str, object] = {"updated_at": utc_now()}
        if content is not None:
            values["content"] = content
        if status is not None:
            values["status"] = status
        async with self._database() as session:
            await session.execute(
                update(ChatMessage).where(ChatMessage.id == message_id).values(values)
            )
            await session.commit()

    async def active_path(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Sequence[ChatMessage]:
        """Root-to-leaf walk of the active branch; server-side LLM context."""
        messages = {
            message.id: message for message in await self.list_messages(owner_id, conversation_id)
        }
        conversation = await self.get_conversation(owner_id, conversation_id)
        leaf = conversation.active_leaf_message_id
        if leaf is not None and leaf not in messages:
            raise ChatError("INVALID_LEAF", 422)
        path: list[ChatMessage] = []
        current = leaf
        while current is not None:
            message = messages.get(current)
            if message is None or len(path) > len(messages):
                raise ChatError("INVALID_LEAF", 422)
            path.append(message)
            current = message.parent_message_id
        path.reverse()
        return path

    # --- drafts and preferences ---------------------------------------

    async def set_draft(self, owner_id: uuid.UUID, key: str, content: str) -> None:
        async with self._database() as session:
            await session.execute(
                pg_insert(ChatDraft)
                .values(owner_id=owner_id, draft_key=key, content=content, updated_at=utc_now())
                .on_conflict_do_update(
                    index_elements=["owner_id", "draft_key"],
                    set_={"content": content, "updated_at": utc_now()},
                )
            )
            await session.commit()

    async def list_drafts(self, owner_id: uuid.UUID) -> Sequence[ChatDraft]:
        async with self._database() as session:
            return (
                await session.scalars(select(ChatDraft).where(ChatDraft.owner_id == owner_id))
            ).all()

    async def delete_draft(self, owner_id: uuid.UUID, key: str) -> None:
        async with self._database() as session:
            await session.execute(
                delete(ChatDraft).where(ChatDraft.owner_id == owner_id, ChatDraft.draft_key == key)
            )
            await session.commit()

    async def get_preferences(self, owner_id: uuid.UUID) -> ChatUserPreferences:
        async with self._database() as session:
            preferences = await session.get(ChatUserPreferences, owner_id)
            if preferences is None:
                preferences = ChatUserPreferences(owner_id=owner_id)
                session.add(preferences)
                await session.commit()
                await session.refresh(preferences)
            return preferences

    async def set_preferences(
        self,
        owner_id: uuid.UUID,
        *,
        active_conversation_id: object | uuid.UUID | None = UNCHANGED,
        model_id: object | str | None = UNCHANGED,
    ) -> ChatUserPreferences:
        async with self._database() as session:
            preferences = await session.get(ChatUserPreferences, owner_id)
            if preferences is None:
                preferences = ChatUserPreferences(owner_id=owner_id)
                session.add(preferences)
            if active_conversation_id is not UNCHANGED:
                preferences.active_conversation_id = active_conversation_id  # type: ignore[assignment]
            if model_id is not UNCHANGED:
                preferences.model_id = model_id  # type: ignore[assignment]
            preferences.updated_at = utc_now()
            await session.commit()
            await session.refresh(preferences)
            return preferences

    # --- generations (used by the WebSocket orchestrator, PR C) --------

    async def create_generation(
        self,
        owner_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        generation_id: uuid.UUID,
        input_message_id: uuid.UUID,
        assistant_message_id: uuid.UUID,
        model_id: str,
        attempt: int,
    ) -> ChatGeneration:
        async with self._database() as session:
            existing = await session.get(ChatGeneration, generation_id)
            if existing is not None:
                return existing
            generation = ChatGeneration(
                id=generation_id,
                conversation_id=conversation_id,
                input_message_id=input_message_id,
                assistant_message_id=assistant_message_id,
                owner_id=owner_id,
                model_id=model_id,
                status="queued",
                attempt=attempt,
            )
            session.add(generation)
            await session.commit()
            await session.refresh(generation)
            return generation

    async def get_generation(self, owner_id: uuid.UUID, generation_id: uuid.UUID) -> ChatGeneration:
        async with self._database() as session:
            generation = await session.get(ChatGeneration, generation_id)
        if generation is None or generation.owner_id != owner_id:
            raise ChatError("GENERATION_NOT_FOUND", 404)
        return generation

    async def set_generation_status(
        self,
        generation_id: uuid.UUID,
        status: str,
        *,
        error_code: str | None = None,
        started: bool = False,
        completed: bool = False,
        cancelled: bool = False,
        last_sequence: int | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status}
        if error_code is not None:
            values["error_code"] = error_code
        if started:
            values["started_at"] = utc_now()
        if completed:
            values["completed_at"] = utc_now()
        if cancelled:
            values["cancelled_at"] = utc_now()
        if last_sequence is not None:
            values["last_sequence"] = last_sequence
        async with self._database() as session:
            await session.execute(
                update(ChatGeneration).where(ChatGeneration.id == generation_id).values(values)
            )
            await session.commit()

    async def append_stream_event(
        self, generation_id: uuid.UUID, sequence: int, event_type: str, payload: dict[str, object]
    ) -> None:
        async with self._database() as session:
            await session.execute(
                insert(ChatStreamEvent).values(
                    generation_id=generation_id,
                    sequence=sequence,
                    event_type=event_type,
                    payload=payload,
                )
            )
            await session.commit()

    async def list_stream_events(
        self, generation_id: uuid.UUID, *, after_sequence: int = 0
    ) -> Sequence[ChatStreamEvent]:
        query = (
            select(ChatStreamEvent)
            .where(
                ChatStreamEvent.generation_id == generation_id,
                ChatStreamEvent.sequence > after_sequence,
            )
            .order_by(ChatStreamEvent.sequence)
        )
        async with self._database() as session:
            return (await session.scalars(query)).all()

    async def mark_running_generations_interrupted(self, owner_id: uuid.UUID) -> int:
        """Startup recovery: no faked completions after a backend restart."""
        async with self._database() as session:
            ids = (
                await session.execute(
                    update(ChatGeneration)
                    .where(
                        ChatGeneration.owner_id == owner_id,
                        ChatGeneration.status.in_(("queued", "running")),
                    )
                    .values(status="interrupted")
                    .returning(ChatGeneration.id)
                )
            ).scalars()
            count = len(ids.all())
            await session.commit()
            return count
