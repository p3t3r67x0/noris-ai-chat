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
        continuationCount=message.continuation_count,
        errorCode=message.error_code,
        errorMessage=message.error_message,
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
        self, owner_id: uuid.UUID, title: str | None, conversation_id: uuid.UUID | None = None
    ) -> ConversationResponse:
        try:
            conversation = await self.repository.create_conversation(
                owner_id,
                title=(title.strip() or FALLBACK_TITLE) if title else FALLBACK_TITLE,
                conversation_id=conversation_id,
            )
        except IntegrityError as error:
            if conversation_id is not None:
                try:
                    return await self.get_conversation(owner_id, conversation_id)
                except ChatError:
                    raise ChatError("MESSAGE_EXISTS", 409) from error
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
        """Prevalidate everything; the repository imports the entire snapshot atomically."""
        if len({c.id for c in request.conversations}) != len(request.conversations) or len(
            {m.id for m in request.messages}
        ) != len(request.messages):
            raise ChatError("IMPORT_INVALID", 422)
        ids = {c.id for c in request.conversations}
        if any(m.conversationId not in ids for m in request.messages):
            raise ChatError("IMPORT_INVALID", 422)
        if request.activeConversationId is not None and request.activeConversationId not in ids:
            raise ChatError("IMPORT_INVALID", 422)
        for key, value in request.drafts.items():
            if (key != NEW_CHAT_DRAFT_KEY and key not in {str(i) for i in ids}) or len(
                value
            ) > 64000:
                raise ChatError("IMPORT_INVALID", 422)
        ordered: list[ImportMessage] = []
        conflicts: list[ImportConflict] = []
        for conversation in request.conversations:
            tree = {m.id: m for m in request.messages if m.conversationId == conversation.id}
            conflict = _validate_import_tree(conversation, tree)
            if conflict is not None:
                conflicts.append(conflict)
            else:
                ordered.extend(_topological_order(tree))
        if conflicts:
            return ChatImportResponse(
                imported=[], skipped=[], conflicts=conflicts, draftsImported=0
            )
        return await self.repository.import_snapshot(owner_id, request, ordered)


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
        if (parent is not None and parent.role == message.role) or (
            parent is None and message.role == "assistant"
        ):
            return ImportConflict(conversationId=conversation.id, reason="invalid_parent")
        if message.editedFromMessageId is not None:
            original = tree.get(message.editedFromMessageId)
            if (
                original is None
                or original.id == message.id
                or original.role != message.role
                or original.parentMessageId != message.parentMessageId
            ):
                return ImportConflict(conversationId=conversation.id, reason="invalid_parent")
        if message.role == "user" and (
            message.status != "completed" or not message.content.strip()
        ):
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
            if (message.parentMessageId is None or message.parentMessageId in placed) and (
                message.editedFromMessageId is None or message.editedFromMessageId in placed
            ):
                ordered.append(message)
                placed.add(message.id)
                remaining.remove(message)
                progressed = True
        if not progressed:
            raise ChatError("IMPORT_INVALID", 422)
    return ordered
