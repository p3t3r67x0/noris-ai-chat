"""Application service for chat persistence (REST level).

Validates ownership, tree integrity and imports; the repository performs all
parameterized database access. The WebSocket generation orchestrator lives in
generation.py and reuses this service.
"""

import uuid
from typing import cast

from sqlalchemy.exc import IntegrityError

from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.repository import ChatRepository
from noris_ai.chat.schemas import (
    ChatImportRequest,
    ChatImportResponse,
    ConversationResponse,
    DraftResponse,
    ImportConflict,
    ImportConversation,
    ImportMessage,
    MessageResponse,
    MessageRole,
    MessageStatus,
    PreferencesResponse,
    TitleSource,
)

FALLBACK_TITLE = "Neuer Chat"
NEW_CHAT_DRAFT_KEY = "__new__"


def conversation_response(conversation: ChatConversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        titleSource=cast(TitleSource, conversation.title_source),
        createdAt=conversation.created_at,
        updatedAt=conversation.updated_at,
        archivedAt=conversation.archived_at,
        version=conversation.version,
        lastMessageAt=conversation.last_message_at,
        activeLeafMessageId=conversation.active_leaf_message_id,
    )


def message_response(message: ChatMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversationId=message.conversation_id,
        parentMessageId=message.parent_message_id,
        role=cast(MessageRole, message.role),
        content=message.content,
        modelId=message.model_id,
        status=cast(MessageStatus, message.status),
        generationId=message.generation_id,
        editedFromMessageId=message.edited_from_message_id,
        createdAt=message.created_at,
        updatedAt=message.updated_at,
    )


class ChatService:
    def __init__(self, repository: ChatRepository) -> None:
        self.repository = repository

    async def create_conversation(
        self, owner_id: uuid.UUID, title: str | None
    ) -> ConversationResponse:
        try:
            conversation = await self.repository.create_conversation(
                owner_id, title=title.strip() if title else FALLBACK_TITLE
            )
        except IntegrityError as error:
            raise ChatError("INVALID_INPUT", 422) from error
        return conversation_response(conversation)

    async def list_conversations(
        self, owner_id: uuid.UUID, *, include_archived: bool
    ) -> list[ConversationResponse]:
        conversations = await self.repository.list_conversations(
            owner_id, include_archived=include_archived
        )
        return [conversation_response(conversation) for conversation in conversations]

    async def get_conversation(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> ConversationResponse:
        return conversation_response(
            await self.repository.get_conversation(owner_id, conversation_id)
        )

    async def rename_conversation(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID, title: str, version: int
    ) -> ConversationResponse:
        conversation = await self.repository.update_conversation(
            owner_id,
            conversation_id,
            expected_version=version,
            title=title.strip(),
            title_source="manual",
        )
        return conversation_response(conversation)

    async def set_archived(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID, archived: bool, version: int
    ) -> ConversationResponse:
        conversation = await self.repository.update_conversation(
            owner_id, conversation_id, expected_version=version, archived=archived
        )
        return conversation_response(conversation)

    async def set_active_leaf(
        self,
        owner_id: uuid.UUID,
        conversation_id: uuid.UUID,
        active_leaf_message_id: uuid.UUID,
        version: int,
    ) -> ConversationResponse:
        # The leaf must be a message of this conversation (repository enforces
        # ownership; the database FK enforces conversation binding).
        messages = await self.repository.list_messages(owner_id, conversation_id)
        if active_leaf_message_id not in {message.id for message in messages}:
            raise ChatError("INVALID_LEAF", 422)
        conversation = await self.repository.update_conversation(
            owner_id,
            conversation_id,
            expected_version=version,
            active_leaf_message_id=active_leaf_message_id,
        )
        return conversation_response(conversation)

    async def delete_conversation(self, owner_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        await self.repository.soft_delete_conversation(owner_id, conversation_id)

    async def list_messages(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[MessageResponse]:
        messages = await self.repository.list_messages(owner_id, conversation_id)
        return [message_response(message) for message in messages]

    async def set_draft(self, owner_id: uuid.UUID, key: str, content: str) -> DraftResponse:
        if not key or len(key) > 64 or key != key.strip():
            raise ChatError("INVALID_INPUT", 422)
        await self.repository.set_draft(owner_id, key, content)
        drafts = {draft.draft_key: draft for draft in await self.repository.list_drafts(owner_id)}
        draft = drafts.get(key)
        if draft is None:  # pragma: no cover - upsert just succeeded
            raise ChatError("INTERNAL_ERROR", 500)
        return DraftResponse(key=draft.draft_key, content=draft.content, updatedAt=draft.updated_at)

    async def list_drafts(self, owner_id: uuid.UUID) -> list[DraftResponse]:
        return [
            DraftResponse(key=draft.draft_key, content=draft.content, updatedAt=draft.updated_at)
            for draft in await self.repository.list_drafts(owner_id)
        ]

    async def clear_draft(self, owner_id: uuid.UUID, key: str) -> None:
        await self.repository.delete_draft(owner_id, key)

    async def get_preferences(self, owner_id: uuid.UUID) -> PreferencesResponse:
        preferences = await self.repository.get_preferences(owner_id)
        return PreferencesResponse(
            activeConversationId=preferences.active_conversation_id,
            modelId=preferences.model_id,
        )

    async def set_preferences(
        self,
        owner_id: uuid.UUID,
        active_conversation_id: object | uuid.UUID | None,
        model_id: object | str | None,
    ) -> PreferencesResponse:
        if isinstance(active_conversation_id, uuid.UUID):
            await self.repository.get_conversation(owner_id, active_conversation_id)
        preferences = await self.repository.set_preferences(
            owner_id,
            active_conversation_id=active_conversation_id,
            model_id=model_id,
        )
        return PreferencesResponse(
            activeConversationId=preferences.active_conversation_id,
            modelId=preferences.model_id,
        )

    async def apply_generated_title(
        self, owner_id: uuid.UUID, conversation_id: uuid.UUID, title: str
    ) -> ConversationResponse | None:
        conversation = await self.repository.set_generated_title(owner_id, conversation_id, title)
        return None if conversation is None else conversation_response(conversation)

    async def import_snapshot(
        self, owner_id: uuid.UUID, request: ChatImportRequest
    ) -> ChatImportResponse:
        """Controlled browser-data import; idempotent and conflict-reporting."""
        imported: list[uuid.UUID] = []
        skipped: list[uuid.UUID] = []
        conflicts: list[ImportConflict] = []
        messages_by_conversation: dict[uuid.UUID, dict[uuid.UUID, ImportMessage]] = {}
        for message in request.messages:
            messages_by_conversation.setdefault(message.conversationId, {})[message.id] = message
        for conversation in request.conversations:
            tree = messages_by_conversation.get(conversation.id, {})
            conflict = _validate_import_tree(conversation, tree)
            try:
                existing = await self.repository.get_conversation(owner_id, conversation.id)
            except ChatError:
                existing = None
            if existing is not None:
                existing_messages = await self.repository.list_messages(owner_id, conversation.id)
                same = (
                    existing.title == conversation.title
                    and existing.title_source == conversation.titleSource
                    and len(existing_messages) == len(tree)
                )
                if same and conflict is None:
                    skipped.append(conversation.id)
                    continue
                conflicts.append(
                    ImportConflict(
                        conversationId=conversation.id, reason="exists_with_different_data"
                    )
                )
                continue
            if conflict is not None:
                conflicts.append(conflict)
                continue
            try:
                await self.repository.create_conversation(
                    owner_id,
                    title=conversation.title,
                    title_source=conversation.titleSource,
                    conversation_id=conversation.id,
                    created_at=conversation.createdAt,
                )
                for message in _topological_order(tree):
                    await self.repository.append_message(
                        ChatMessage(
                            id=message.id,
                            conversation_id=conversation.id,
                            parent_message_id=message.parentMessageId,
                            role=message.role,
                            content=message.content,
                            model_id=message.modelId,
                            status=message.status,
                            generation_id=None,
                            edited_from_message_id=message.editedFromMessageId,
                            created_at=message.createdAt,
                            updated_at=message.updatedAt,
                        )
                    )
            except (IntegrityError, ChatError) as error:
                raise ChatError("IMPORT_INVALID", 422) from error
            leaf = conversation.activeLeafMessageId
            if leaf is not None:
                await self.repository.update_conversation(
                    owner_id,
                    conversation.id,
                    expected_version=1,
                    active_leaf_message_id=leaf,
                )
            imported.append(conversation.id)
        drafts_imported = 0
        for key, content in request.drafts.items():
            if key == NEW_CHAT_DRAFT_KEY or key in {
                str(conversation.id) for conversation in request.conversations
            }:
                await self.repository.set_draft(owner_id, key, content)
                drafts_imported += 1
        return ChatImportResponse(
            imported=imported,
            skipped=skipped,
            conflicts=conflicts,
            draftsImported=drafts_imported,
        )


def _validate_import_tree(
    conversation: ImportConversation, tree: dict[uuid.UUID, ImportMessage]
) -> ImportConflict | None:
    leaf = conversation.activeLeafMessageId
    if leaf is not None and leaf not in tree:
        return ImportConflict(conversationId=conversation.id, reason="invalid_leaf")
    for message in tree.values():
        parent = tree.get(message.parentMessageId) if message.parentMessageId else None
        if message.parentMessageId is not None and parent is None:
            return ImportConflict(conversationId=conversation.id, reason="invalid_parent")
        if parent is not None and parent.role == message.role:
            return ImportConflict(conversationId=conversation.id, reason="invalid_parent")
        if message.role == "user" and message.status != "completed":
            return ImportConflict(conversationId=conversation.id, reason="invalid_parent")
    return None


def _topological_order(
    tree: dict[uuid.UUID, ImportMessage],
) -> list[ImportMessage]:
    """Parents first; the import only inserts acyclic trees."""
    ordered: list[ImportMessage] = []
    placed: set[uuid.UUID] = set()
    remaining = sorted(tree.values(), key=lambda message: message.createdAt)
    while remaining:
        progressed = False
        for message in list(remaining):
            if message.parentMessageId is None or message.parentMessageId in placed:
                ordered.append(message)
                placed.add(message.id)
                remaining.remove(message)
                progressed = True
        if not progressed:
            raise ChatError("IMPORT_INVALID", 422)
    return ordered
