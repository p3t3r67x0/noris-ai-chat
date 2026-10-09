"""Pydantic contracts for the chat REST API (Etappe 3).

Field names follow the existing camelCase API conventions; every schema is
strict, frozen and forbids extras. Ownership is server-side only and never
accepted from clients.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from noris_ai.core.schemas import ApiSchema

TitleSource = Literal["fallback", "generated", "manual"]
MessageRole = Literal["user", "assistant"]
MessageStatus = Literal["pending", "streaming", "completed", "incomplete", "cancelled", "failed"]
GenerationStatus = Literal[
    "queued", "running", "completed", "incomplete", "cancelled", "failed", "interrupted"
]

MAX_MESSAGE_LENGTH = 32_000
MAX_TITLE_LENGTH = 120
MAX_DRAFT_LENGTH = MAX_MESSAGE_LENGTH * 2
MAX_IMPORT_CONVERSATIONS = 500
MAX_IMPORT_MESSAGES = 10_000


class JsonApiSchema(ApiSchema):
    """Chat contract: JSON input parsing (datetime/UUID from strings) allowed."""

    model_config = ApiSchema.model_config | {"strict": False}


class ConversationCreate(JsonApiSchema):
    id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)


class ConversationUpdate(JsonApiSchema):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    archived: bool | None = None
    activeLeafMessageId: UUID | None = None
    version: int = Field(ge=1)


class ConversationResponse(JsonApiSchema):
    id: UUID
    title: str
    titleSource: TitleSource
    createdAt: datetime
    updatedAt: datetime
    archivedAt: datetime | None
    version: int
    lastMessageAt: datetime | None
    activeLeafMessageId: UUID | None


class ConversationListResponse(JsonApiSchema):
    conversations: list[ConversationResponse]


class MessageResponse(JsonApiSchema):
    id: UUID
    conversationId: UUID
    parentMessageId: UUID | None
    role: MessageRole
    content: str
    modelId: str | None
    continuationCount: int = 0
    errorCode: str | None = None
    errorMessage: str | None = None
    status: MessageStatus
    generationId: UUID | None
    editedFromMessageId: UUID | None
    createdAt: datetime
    updatedAt: datetime


class MessageListResponse(JsonApiSchema):
    messages: list[MessageResponse]


class DraftUpdate(JsonApiSchema):
    content: str = Field(max_length=MAX_DRAFT_LENGTH)


class DraftResponse(JsonApiSchema):
    key: str
    content: str
    updatedAt: datetime


class DraftListResponse(JsonApiSchema):
    drafts: list[DraftResponse]


class PreferencesResponse(JsonApiSchema):
    activeConversationId: UUID | None
    modelId: str | None


class PreferencesUpdate(JsonApiSchema):
    activeConversationId: UUID | None = None
    modelId: str | None = Field(default=None, max_length=200)


class ImportMessage(JsonApiSchema):
    id: UUID
    conversationId: UUID
    parentMessageId: UUID | None = None
    role: MessageRole
    content: str = Field(max_length=1_048_576)
    status: MessageStatus
    modelId: str | None = Field(default=None, max_length=200)
    continuationCount: int = Field(default=0, ge=0, le=20)
    errorCode: str | None = Field(default=None, max_length=100)
    errorMessage: str | None = Field(default=None, max_length=1000)
    editedFromMessageId: UUID | None = None
    createdAt: datetime
    updatedAt: datetime


class ImportConversation(JsonApiSchema):
    id: UUID
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    titleSource: TitleSource
    createdAt: datetime
    updatedAt: datetime
    archivedAt: datetime | None = None
    activeLeafMessageId: UUID | None = None
    version: int = Field(default=1, ge=1)


class ChatImportRequest(JsonApiSchema):
    conversations: list[ImportConversation] = Field(max_length=MAX_IMPORT_CONVERSATIONS)
    messages: list[ImportMessage] = Field(max_length=MAX_IMPORT_MESSAGES)
    drafts: dict[str, str] = Field(default_factory=dict)
    activeConversationId: UUID | None = None


class ImportConflict(JsonApiSchema):
    conversationId: UUID
    reason: Literal[
        "exists_with_different_data", "invalid_parent", "invalid_leaf", "duplicate_message"
    ]


class ChatImportResponse(JsonApiSchema):
    imported: list[UUID]
    skipped: list[UUID]
    conflicts: list[ImportConflict]
    draftsImported: int
