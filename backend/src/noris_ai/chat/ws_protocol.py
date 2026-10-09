"""Versioned WebSocket protocol contract (chat v1).

OpenAPI does not describe WebSockets; this module is the single source of
truth mirrored by docs/websocket/chat-v1.json and checked for drift in CI.
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from noris_ai.chat.schemas import (
    ConversationResponse,
    GenerationStatus,
    JsonApiSchema,
    MessageResponse,
)

PROTOCOL_VERSION = 1
MAX_INPUT_LENGTH = 32_000


class ClientEnvelope(JsonApiSchema):
    version: Literal[1]


class GenerateIncomingMessage(ClientEnvelope):
    type: Literal["chat.generate"]
    requestId: UUID  # generation id, idempotent
    conversationId: UUID
    inputMessageId: UUID
    modelId: str = Field(max_length=200)
    assistantMessageId: UUID
    conversationVersion: int = Field(ge=1)
    editedFromMessageId: UUID | None = None
    operation: Literal["generate", "continue"] = "generate"
    sourceAssistantMessageId: UUID | None = None
    attempt: int = Field(default=1, ge=1, le=1000)
    parentMessageId: UUID | None = None
    content: str = Field(min_length=1, max_length=MAX_INPUT_LENGTH)


class CancelIncomingMessage(ClientEnvelope):
    type: Literal["chat.cancel"]
    generationId: UUID


class ResumeIncomingMessage(ClientEnvelope):
    type: Literal["chat.resume"]
    generationId: UUID
    lastReceivedSeq: int = Field(default=0, ge=0)


class PingIncomingMessage(ClientEnvelope):
    type: Literal["chat.ping"]


ClientMessage = (
    GenerateIncomingMessage | CancelIncomingMessage | ResumeIncomingMessage | PingIncomingMessage
)


class ServerEnvelope(JsonApiSchema):
    model_config = JsonApiSchema.model_config | {
        "json_schema_serialization_defaults_required": True
    }
    version: Literal[1] = PROTOCOL_VERSION


class ConnectedEvent(ServerEnvelope):
    type: Literal["chat.connected"] = "chat.connected"
    heartbeatSeconds: int


class MessageCreatedEvent(ServerEnvelope):
    type: Literal["chat.message.created"] = "chat.message.created"
    conversationId: UUID
    message: MessageResponse


class GenerationStartedEvent(ServerEnvelope):
    type: Literal["chat.generation.started"] = "chat.generation.started"
    generationId: UUID
    conversationId: UUID
    messageId: UUID
    modelId: str
    seq: int


class GenerationDeltaEvent(ServerEnvelope):
    type: Literal["chat.generation.delta"] = "chat.generation.delta"
    generationId: UUID
    conversationId: UUID
    messageId: UUID
    seq: int = Field(ge=1)
    delta: str


class GenerationTerminalEvent(ServerEnvelope):
    """Shared terminal fields; the type discriminates completion states."""

    generationId: UUID
    conversationId: UUID
    messageId: UUID
    seq: int = Field(ge=1)
    content: str


class GenerationCompletedEvent(GenerationTerminalEvent):
    type: Literal["chat.generation.completed"] = "chat.generation.completed"


class GenerationIncompleteEvent(GenerationTerminalEvent):
    type: Literal["chat.generation.incomplete"] = "chat.generation.incomplete"
    reason: Literal["output_limit"] = "output_limit"


class GenerationFailedEvent(GenerationTerminalEvent):
    type: Literal["chat.generation.failed"] = "chat.generation.failed"
    code: str
    message: str


class GenerationCancelledEvent(GenerationTerminalEvent):
    type: Literal["chat.generation.cancelled"] = "chat.generation.cancelled"


class GenerationInterruptedEvent(GenerationTerminalEvent):
    type: Literal["chat.generation.interrupted"] = "chat.generation.interrupted"


class ConversationUpdatedEvent(ServerEnvelope):
    type: Literal["chat.conversation.updated"] = "chat.conversation.updated"
    conversation: ConversationResponse


class TitleUpdatedEvent(ServerEnvelope):
    type: Literal["chat.title.updated"] = "chat.title.updated"
    conversationId: UUID
    title: str
    titleSource: str


class ResumeAcceptedEvent(ServerEnvelope):
    type: Literal["chat.resume.accepted"] = "chat.resume.accepted"
    generationId: UUID
    lastReceivedSeq: int


class ResumeSnapshotEvent(ServerEnvelope):
    type: Literal["chat.resume.snapshot"] = "chat.resume.snapshot"
    generationId: UUID
    conversationId: UUID
    messageId: UUID
    status: GenerationStatus
    content: str
    lastSequence: int


class ErrorEvent(ServerEnvelope):
    type: Literal["chat.error"] = "chat.error"
    code: str
    message: str
    requestId: UUID | None = None


class HeartbeatEvent(ServerEnvelope):
    type: Literal["chat.heartbeat"] = "chat.heartbeat"


class PongEvent(ServerEnvelope):
    type: Literal["chat.pong"] = "chat.pong"


ServerEvent = (
    ConnectedEvent
    | MessageCreatedEvent
    | GenerationStartedEvent
    | GenerationDeltaEvent
    | GenerationCompletedEvent
    | GenerationIncompleteEvent
    | GenerationFailedEvent
    | GenerationCancelledEvent
    | GenerationInterruptedEvent
    | ConversationUpdatedEvent
    | TitleUpdatedEvent
    | ResumeAcceptedEvent
    | ResumeSnapshotEvent
    | ErrorEvent
    | HeartbeatEvent
    | PongEvent
)
