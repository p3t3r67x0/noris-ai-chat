"""Chat persistence domain models (Etappe 3).

PostgreSQL is the source of truth for conversations, the message tree
(immutable branches), generations, replayable stream events, drafts and
per-owner preferences. Browser storage is a cache only.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from noris_ai.db.base import Base

TITLE_SOURCE_ENUM = Enum(
    "fallback", "generated", "manual", name="chat_title_source", validate_strings=True
)
MESSAGE_ROLE_ENUM = Enum("user", "assistant", name="chat_message_role", validate_strings=True)
MESSAGE_STATUS_ENUM = Enum(
    "pending",
    "streaming",
    "completed",
    "incomplete",
    "cancelled",
    "failed",
    name="chat_message_status",
    validate_strings=True,
)
GENERATION_STATUS_ENUM = Enum(
    "queued",
    "running",
    "completed",
    "incomplete",
    "cancelled",
    "failed",
    "interrupted",
    name="chat_generation_status",
    validate_strings=True,
)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ChatConversation(Base):
    __tablename__ = "chat_conversation"
    __table_args__ = (
        CheckConstraint("length(title) > 0 AND length(title) <= 200", name="title_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        # The active leaf must belong to this conversation.
        ForeignKeyConstraint(
            ["id", "active_leaf_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="active_leaf",
            use_alter=True,
        ),
        Index("ix_chat_conversation_owner_updated", "owner_id", "updated_at"),
        Index(
            "ix_chat_conversation_seek",
            "owner_id",
            text("updated_at DESC"),
            text("id DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_chat_conversation_active_seek",
            "owner_id",
            text("updated_at DESC"),
            text("id DESC"),
            postgresql_where=text("deleted_at IS NULL AND archived_at IS NULL"),
        ),
        Index(
            "ix_chat_conversation_title_search",
            text("lower(title) gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_source: Mapped[str] = mapped_column(TITLE_SOURCE_ENUM, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_leaf_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = (
        # A parent must be a message of the same conversation.
        ForeignKeyConstraint(
            ["conversation_id", "parent_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="parent",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "edited_from_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="edited_from",
        ),
        UniqueConstraint("conversation_id", "id", name="uq_chat_message_conversation_id"),
        CheckConstraint("length(content) <= 1048576", name="content_length"),
        Index("ix_chat_message_conversation_created", "conversation_id", "created_at"),
        Index("ix_chat_message_seek", "conversation_id", text("created_at DESC"), text("id DESC")),
        Index(
            "ix_chat_message_siblings",
            "conversation_id",
            "parent_message_id",
            "role",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_conversation.id"), nullable=False
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(MESSAGE_ROLE_ENUM, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str | None] = mapped_column(Text)
    continuation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(MESSAGE_STATUS_ENUM, nullable=False)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("chat_generation.id"))
    edited_from_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ChatGeneration(Base):
    __tablename__ = "chat_generation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "source_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="source_message",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["conversation_id", "input_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="input_message",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["conversation_id", "assistant_message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="assistant_message",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversation.id"], name="fk_chat_generation_conversation"
        ),
        CheckConstraint(
            "output_tokens IS NULL AND input_tokens IS NULL"
            " OR output_tokens IS NOT NULL AND input_tokens IS NOT NULL",
            name="usage_complete",
        ),
        Index("ix_chat_generation_conversation", "conversation_id"),
        Index("ix_chat_generation_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    input_message_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(GENERATION_STATUS_ENUM, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    operation: Mapped[str] = mapped_column(Text, nullable=False, server_default="generate")
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    # Measured provider usage only. The provider reports none; estimates are
    # never persisted as measurements.
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ChatStreamEvent(Base):
    __tablename__ = "chat_stream_event"
    __table_args__ = (
        PrimaryKeyConstraint("generation_id", "sequence", name="pk_chat_stream_event"),
        ForeignKeyConstraint(
            ["generation_id"], ["chat_generation.id"], name="fk_chat_stream_event_generation"
        ),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        Index("ix_chat_stream_event_generation_sequence", "generation_id", "sequence"),
        Index("ix_chat_stream_event_created", "created_at"),
    )

    generation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ChatDraft(Base):
    __tablename__ = "chat_draft"
    __table_args__ = (
        CheckConstraint("length(draft_key) > 0 AND length(draft_key) <= 64", name="key_length"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    draft_key: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ChatUserPreferences(Base):
    __tablename__ = "chat_user_preferences"

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    active_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("chat_conversation.id")
    )
    model_id: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
