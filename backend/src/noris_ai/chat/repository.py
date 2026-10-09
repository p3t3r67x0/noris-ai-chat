"""SQLAlchemy repository for chat persistence.

Every query is scoped to the server-side owner; clients can never supply or
override ownership. The message tree is append-only: edits and regenerations
create siblings instead of overwriting messages.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

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
from noris_ai.chat.schemas import (
    ChatImportRequest,
    ChatImportResponse,
    ImportConflict,
    ImportMessage,
    MessageStatus,
    TitleSource,
)
from noris_ai.chat.ws_protocol import GenerateIncomingMessage

ModelDatabase = async_sessionmaker[AsyncSession]
UNCHANGED = object()


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChatRepository:
    def __init__(self, database: ModelDatabase) -> None:
        self._database = database

    async def import_snapshot(
        self, owner_id: uuid.UUID, request: ChatImportRequest, ordered: list[ImportMessage]
    ) -> ChatImportResponse:
        async with self._database() as session, session.begin():
            # Serialize imports and other resource mutations for this owner.
            await session.execute(
                pg_insert(ChatUserPreferences).values(owner_id=owner_id).on_conflict_do_nothing()
            )
            preferences = await session.scalar(
                select(ChatUserPreferences)
                .where(ChatUserPreferences.owner_id == owner_id)
                .with_for_update()
            )
            skipped: list[uuid.UUID] = []
            conflicts: list[ImportConflict] = []
            for c in request.conversations:
                existing = await session.get(ChatConversation, c.id)
                tree = [m for m in ordered if m.conversationId == c.id]
                if existing is not None:
                    rows = (
                        await session.scalars(
                            select(ChatMessage).where(ChatMessage.conversation_id == c.id)
                        )
                    ).all()
                    by_id = {m.id: m for m in rows}
                    same = (
                        existing.owner_id == owner_id
                        and existing.deleted_at is None
                        and existing.title == c.title
                        and existing.title_source == c.titleSource
                        and existing.active_leaf_message_id == c.activeLeafMessageId
                        and existing.archived_at == c.archivedAt
                        and len(rows) == len(tree)
                        and all(
                            m.id in by_id
                            and (
                                by_id[m.id].content == m.content
                                and by_id[m.id].role == m.role
                                and by_id[m.id].status == m.status
                                and by_id[m.id].model_id == m.modelId
                                and by_id[m.id].parent_message_id == m.parentMessageId
                                and by_id[m.id].edited_from_message_id == m.editedFromMessageId
                                and by_id[m.id].continuation_count == m.continuationCount
                            )
                            for m in tree
                        )
                    )
                    if same:
                        skipped.append(c.id)
                    else:
                        conflicts.append(
                            ImportConflict(conversationId=c.id, reason="exists_with_different_data")
                        )
                elif any([await session.get(ChatMessage, m.id) is not None for m in tree]):
                    conflicts.append(
                        ImportConflict(conversationId=c.id, reason="duplicate_message")
                    )
            if conflicts:
                return ChatImportResponse(
                    imported=[], skipped=skipped, conflicts=conflicts, draftsImported=0
                )
            imported: list[uuid.UUID] = []
            for c in request.conversations:
                if c.id in skipped:
                    continue
                conversation = ChatConversation(
                    id=c.id,
                    owner_id=owner_id,
                    title=c.title,
                    title_source=c.titleSource,
                    created_at=c.createdAt,
                    updated_at=c.updatedAt,
                    archived_at=c.archivedAt,
                    version=1,
                )
                session.add(conversation)
                await session.flush()
                for m in ordered:
                    if m.conversationId != c.id:
                        continue
                    session.add(
                        ChatMessage(
                            id=m.id,
                            conversation_id=c.id,
                            parent_message_id=m.parentMessageId,
                            role=m.role,
                            content=m.content,
                            model_id=m.modelId,
                            continuation_count=m.continuationCount,
                            error_code=m.errorCode,
                            error_message=m.errorMessage,
                            status=m.status,
                            edited_from_message_id=m.editedFromMessageId,
                            created_at=m.createdAt,
                            updated_at=m.updatedAt,
                        )
                    )
                    await session.flush()
                conversation.active_leaf_message_id = c.activeLeafMessageId
                conversation.last_message_at = max(
                    (m.createdAt for m in ordered if m.conversationId == c.id), default=None
                )
                imported.append(c.id)
            drafts_imported = 0
            for key, content in request.drafts.items():
                if key != "__new__" and key not in {str(i) for i in imported}:
                    continue
                if await session.get(ChatDraft, (owner_id, key)) is None:
                    session.add(ChatDraft(owner_id=owner_id, draft_key=key, content=content))
                    drafts_imported += 1
            if preferences is not None and preferences.active_conversation_id is None and imported:
                preferences.active_conversation_id = request.activeConversationId
            return ChatImportResponse(
                imported=imported, skipped=skipped, conflicts=[], draftsImported=drafts_imported
            )

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
            conversation = await session.scalar(
                select(ChatConversation)
                .where(ChatConversation.id == conversation_id)
                .with_for_update()
            )
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
            conversation = await session.scalar(
                select(ChatConversation)
                .where(ChatConversation.id == conversation_id)
                .with_for_update()
            )
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
        async with self._database() as session, session.begin():
            await session.execute(
                pg_insert(ChatUserPreferences).values(owner_id=owner_id).on_conflict_do_nothing()
            )
            preferences = await session.get(ChatUserPreferences, owner_id)
            if preferences is None:  # pragma: no cover - insert just succeeded
                raise ChatError("INTERNAL_ERROR", 500)
            return preferences

    async def set_preferences(
        self,
        owner_id: uuid.UUID,
        *,
        active_conversation_id: object | uuid.UUID | None = UNCHANGED,
        model_id: object | str | None = UNCHANGED,
    ) -> ChatUserPreferences:
        values: dict[str, object] = {"owner_id": owner_id, "updated_at": utc_now()}
        if active_conversation_id is not UNCHANGED:
            values["active_conversation_id"] = active_conversation_id
        if model_id is not UNCHANGED:
            values["model_id"] = model_id
        async with self._database() as session, session.begin():
            row = await session.scalar(
                pg_insert(ChatUserPreferences)
                .values(values)
                .on_conflict_do_update(
                    index_elements=["owner_id"],
                    set_={key: value for key, value in values.items() if key != "owner_id"},
                )
                .returning(ChatUserPreferences)
            )
            if row is None:  # pragma: no cover - returning from an upsert
                raise ChatError("INTERNAL_ERROR", 500)
            return row

    # --- generations (used by the WebSocket orchestrator, PR C) --------

    async def get_generation(self, owner_id: uuid.UUID, generation_id: uuid.UUID) -> ChatGeneration:
        async with self._database() as session:
            generation = await session.get(ChatGeneration, generation_id)
        if generation is None or generation.owner_id != owner_id:
            raise ChatError("GENERATION_NOT_FOUND", 404)
        return generation

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
                    .values(status="interrupted", completed_at=utc_now(), error_code="INTERRUPTED")
                    .returning(ChatGeneration.id)
                )
            ).scalars()
            generation_ids = ids.all()
            count = len(generation_ids)
            await session.execute(
                update(ChatMessage)
                .where(ChatMessage.generation_id.in_(generation_ids))
                .values(status="failed", updated_at=utc_now())
            )
            await session.commit()
            return count

    async def begin_generation(
        self, owner_id: uuid.UUID, command: "GenerateIncomingMessage"
    ) -> tuple[ChatGeneration, list[ChatMessage], bool]:
        """Lock the conversation; accept input and generation atomically, once."""
        async with self._database() as session, session.begin():
            conversation = await session.scalar(
                select(ChatConversation)
                .where(ChatConversation.id == command.conversationId)
                .with_for_update()
            )
            if (
                conversation is None
                or conversation.owner_id != owner_id
                or conversation.deleted_at is not None
                or conversation.archived_at is not None
            ):
                raise ChatError("NOT_FOUND", 404)
            existing = await session.get(ChatGeneration, command.requestId)
            if existing is not None:
                if (
                    existing.owner_id != owner_id
                    or existing.conversation_id != command.conversationId
                    or existing.input_message_id != command.inputMessageId
                    or existing.assistant_message_id != command.assistantMessageId
                    or existing.model_id != command.modelId
                    or existing.operation != command.operation
                    or existing.source_message_id != command.sourceAssistantMessageId
                ):
                    raise ChatError("MESSAGE_EXISTS", 409)
                message = await session.get(ChatMessage, command.inputMessageId)
                if (
                    message is None
                    or message.content != command.content
                    or message.parent_message_id != command.parentMessageId
                ):
                    raise ChatError("MESSAGE_EXISTS", 409)
                return existing, [], False
            if conversation.version != command.conversationVersion:
                raise ChatError("VERSION_CONFLICT", 409)
            running = await session.scalar(
                select(ChatGeneration.id).where(
                    ChatGeneration.conversation_id == conversation.id,
                    ChatGeneration.status.in_(("queued", "running")),
                )
            )
            if running is not None:
                raise ChatError("GENERATION_ACTIVE", 409)
            tree = {
                m.id: m
                for m in (
                    await session.scalars(
                        select(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
                    )
                ).all()
            }
            input_message = await session.get(ChatMessage, command.inputMessageId)
            if input_message is not None:
                if (
                    input_message.conversation_id != conversation.id
                    or input_message.role != "user"
                    or input_message.content != command.content
                    or input_message.parent_message_id != command.parentMessageId
                ):
                    raise ChatError("MESSAGE_EXISTS", 409)
            else:
                parent = tree.get(command.parentMessageId) if command.parentMessageId else None
                if command.parentMessageId and (parent is None or parent.role != "assistant"):
                    raise ChatError("INVALID_PARENT", 422)
                if command.editedFromMessageId:
                    original = tree.get(command.editedFromMessageId)
                    if (
                        original is None
                        or original.role != "user"
                        or original.parent_message_id != command.parentMessageId
                    ):
                        raise ChatError("INVALID_PARENT", 422)
                elif command.parentMessageId != conversation.active_leaf_message_id:
                    raise ChatError("INVALID_LEAF", 422)
                input_message = ChatMessage(
                    id=command.inputMessageId,
                    conversation_id=conversation.id,
                    parent_message_id=command.parentMessageId,
                    role="user",
                    content=command.content,
                    status="completed",
                    created_at=utc_now(),
                    edited_from_message_id=command.editedFromMessageId,
                )
                session.add(input_message)
                await session.flush()
                tree[input_message.id] = input_message
            path: list[ChatMessage] = []
            cursor: uuid.UUID | None = input_message.id
            seen: set[uuid.UUID] = set()
            while cursor is not None:
                if cursor in seen or cursor not in tree:
                    raise ChatError("INVALID_LEAF", 422)
                seen.add(cursor)
                node = tree[cursor]
                path.append(node)
                cursor = node.parent_message_id
            path.reverse()
            prefix, continuation_count = "", 0
            if command.operation == "continue":
                source = (
                    tree.get(command.sourceAssistantMessageId)
                    if command.sourceAssistantMessageId
                    else None
                )
                if (
                    source is None
                    or source.role != "assistant"
                    or source.parent_message_id != input_message.id
                    or source.id != conversation.active_leaf_message_id
                    or source.status not in ("incomplete", "cancelled", "failed")
                    or not source.content
                    or source.model_id != command.modelId
                ):
                    raise ChatError("INVALID_MESSAGE", 422)
                prefix = source.content
                continuation_count = source.continuation_count + 1
                path.append(source)
            elif command.sourceAssistantMessageId is not None:
                raise ChatError("INVALID_INPUT", 422)
            generation = ChatGeneration(
                id=command.requestId,
                conversation_id=conversation.id,
                owner_id=owner_id,
                input_message_id=input_message.id,
                assistant_message_id=None,
                model_id=command.modelId,
                status="queued",
                attempt=command.attempt,
                operation=command.operation,
                source_message_id=command.sourceAssistantMessageId,
            )
            session.add(generation)
            await session.flush()
            session.add(
                ChatMessage(
                    id=command.assistantMessageId,
                    conversation_id=conversation.id,
                    parent_message_id=input_message.id,
                    role="assistant",
                    content=prefix,
                    created_at=utc_now(),
                    continuation_count=continuation_count,
                    model_id=command.modelId,
                    status="pending",
                    generation_id=generation.id,
                )
            )
            await session.flush()
            generation.assistant_message_id = command.assistantMessageId
            conversation.active_leaf_message_id = command.assistantMessageId
            conversation.version += 1
            conversation.updated_at = conversation.last_message_at = utc_now()
            await session.execute(
                delete(ChatDraft).where(
                    ChatDraft.owner_id == owner_id,
                    ChatDraft.draft_key.in_((str(conversation.id), "__new__")),
                )
            )
            return generation, path, True

    async def persist_generation_event(
        self,
        generation_id: uuid.UUID,
        payload: dict[str, object],
        content: str,
        status: str = "running",
        error_code: str | None = None,
    ) -> None:
        """Answer snapshot, sequence and replay event commit together before delivery."""
        async with self._database() as session, session.begin():
            generation = await session.get(ChatGeneration, generation_id)
            if generation is None or generation.status not in ("queued", "running"):
                raise ChatError("GENERATION_NOT_FOUND", 404)
            sequence = payload["seq"]
            if sequence != generation.last_sequence + 1:
                raise ChatError("INVALID_INPUT", 422)
            generation.last_sequence = int(str(sequence))
            generation.status = status
            generation.error_code = error_code
            if generation.started_at is None:
                generation.started_at = utc_now()
            if status not in ("running", "queued"):
                generation.completed_at = utc_now()
            if status == "cancelled":
                generation.cancelled_at = utc_now()
            message = await session.get(ChatMessage, generation.assistant_message_id)
            if message is None:
                raise ChatError("NOT_FOUND", 404)
            message.content = content
            message.status = (
                "streaming"
                if status == "running"
                else ("failed" if status == "interrupted" else status)
            )
            message.updated_at = utc_now()
            message.error_code = error_code
            message.error_message = str(payload["message"]) if "message" in payload else None
            session.add(
                ChatStreamEvent(
                    generation_id=generation.id,
                    sequence=generation.last_sequence,
                    event_type=str(payload["type"]),
                    payload=payload,
                )
            )

    async def prune_stream_events(self, hours: int) -> None:
        async with self._database() as session, session.begin():
            await session.execute(
                delete(ChatStreamEvent).where(
                    ChatStreamEvent.generation_id.in_(
                        select(ChatGeneration.id).where(
                            ChatGeneration.completed_at < utc_now() - timedelta(hours=hours),
                            ChatGeneration.status.not_in(("queued", "running")),
                        )
                    )
                )
            )
