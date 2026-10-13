"""Additive tool tables on the existing shared PostgreSQL metadata."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from noris_ai.db.base import Base


class ToolRun(Base):
    __tablename__ = "chat_tool_run"
    __table_args__ = (
        CheckConstraint("event_sequence >= 0", name="tool_event_sequence"),
        ForeignKeyConstraint(
            ["owner_id", "id", "reservation_id"],
            [
                "chat_budget_reservation.owner_id",
                "chat_budget_reservation.run_id",
                "chat_budget_reservation.id",
            ],
            name="tool_reservation",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["owner_id", "conversation_id"],
            ["chat_conversation.owner_id", "chat_conversation.id"],
            name="tool_conversation",
        ),
        ForeignKeyConstraint(
            ["owner_id", "conversation_id", "generation_id"],
            ["chat_generation.owner_id", "chat_generation.conversation_id", "chat_generation.id"],
            name="tool_generation",
        ),
        ForeignKeyConstraint(
            ["owner_id", "conversation_id", "generation_id", "parent_run_id"],
            [
                "chat_tool_run.owner_id",
                "chat_tool_run.conversation_id",
                "chat_tool_run.generation_id",
                "chat_tool_run.id",
            ],
            name="tool_parent",
        ),
        UniqueConstraint("generation_id", "step_key", name="uq_chat_tool_run_step"),
        UniqueConstraint("owner_id", "id", name="uq_chat_tool_run_owner_id"),
        UniqueConstraint(
            "owner_id", "conversation_id", "generation_id", "id", name="uq_chat_tool_run_scope"
        ),
        UniqueConstraint("owner_id", "id", "input_digest", name="uq_chat_tool_run_input"),
        UniqueConstraint("id", "provider_key", "config_version", name="uq_chat_tool_run_provider"),
        CheckConstraint(
            "parent_run_id IS NULL OR parent_run_id <> id", name="tool_parent_not_self"
        ),
        CheckConstraint(
            "tool_id ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+\\.v[1-9][0-9]*$'"
            " AND length(tool_id) <= 100",
            name="tool_id",
        ),
        CheckConstraint("schema_version >= 1 AND attempt >= 1", name="tool_versions"),
        CheckConstraint("length(step_key) BETWEEN 1 AND 100", name="tool_step_key"),
        CheckConstraint(
            "invocation_kind IN ('web_mode', 'research_step', 'user_action')",
            name="tool_invocation",
        ),
        CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="tool_input_digest"),
        CheckConstraint(
            "jsonb_typeof(input) = 'object' AND octet_length(input::text) <= 65536",
            name="tool_input_size",
        ),
        CheckConstraint(
            "(provider_key IS NULL) = (config_version IS NULL)", name="tool_provider_pair"
        ),
        CheckConstraint(
            "length(provider_key) BETWEEN 1 AND 100 AND length(config_version) BETWEEN 1 AND 100",
            name="tool_provider_size",
        ),
        CheckConstraint(
            "state IN ('queued', 'awaiting_approval', 'running', 'succeeded', 'failed',"
            " 'cancelled', 'timed_out', 'interrupted', 'outcome_unknown')",
            name="tool_state",
        ),
        CheckConstraint(
            "(state IN ('queued', 'awaiting_approval', 'running')) = (finished_at IS NULL)",
            name="tool_finished",
        ),
        CheckConstraint("state <> 'running' OR started_at IS NOT NULL", name="tool_started"),
        CheckConstraint("length(error_code) BETWEEN 1 AND 100", name="tool_error_size"),
        CheckConstraint(
            "policy_snapshot IS NULL OR (jsonb_typeof(policy_snapshot) = 'object' "
            "AND octet_length(policy_snapshot::text) <= 2048)",
            name="tool_policy_size",
        ),
        CheckConstraint(
            "dispatched_at IS NULL OR (execution_id IS NOT NULL AND reservation_id IS NOT NULL)",
            name="tool_dispatch",
        ),
        Index("ix_chat_tool_run_owner_generation", "owner_id", "generation_id"),
        Index("ix_chat_tool_run_state_deadline", "state", "deadline_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    generation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    parent_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    tool_id: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    invocation_kind: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    input_digest: Mapped[str] = mapped_column(Text, nullable=False)
    provider_key: Mapped[str | None] = mapped_column(Text)
    config_version: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reservation_id: Mapped[UUID | None] = mapped_column(Uuid)
    execution_id: Mapped[UUID | None] = mapped_column(Uuid)
    execution_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_id: Mapped[UUID | None] = mapped_column(Uuid)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    event_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolResult(Base):
    __tablename__ = "chat_tool_result"
    __table_args__ = (
        CheckConstraint("result_version >= 1", name="tool_result_version"),
        CheckConstraint("length(output_schema) BETWEEN 1 AND 100", name="tool_output_schema"),
        CheckConstraint(
            "jsonb_typeof(output) = 'object' AND octet_length(output::text) <= 262144",
            name="tool_output_size",
        ),
        CheckConstraint("result_digest ~ '^[0-9a-f]{64}$'", name="tool_result_digest"),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_tool_run.id"), primary_key=True)
    result_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    output_schema: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ToolApproval(Base):
    __tablename__ = "chat_tool_approval"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "run_id", "input_digest"],
            ["chat_tool_run.owner_id", "chat_tool_run.id", "chat_tool_run.input_digest"],
            name="approval_input",
        ),
        ForeignKeyConstraint(
            ["run_id", "provider_key", "config_version"],
            ["chat_tool_run.id", "chat_tool_run.provider_key", "chat_tool_run.config_version"],
            name="approval_provider",
        ),
        UniqueConstraint("decision_request_id", name="uq_chat_tool_approval_decision"),
        CheckConstraint(
            "state IN ('pending', 'approved', 'denied', 'expired')", name="approval_state"
        ),
        CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="approval_digest"),
        CheckConstraint("length(permission_scope) BETWEEN 1 AND 200", name="approval_scope"),
        CheckConstraint(
            "max_calls >= 1 AND max_cost >= 0 AND max_cost <> 'NaN'::numeric",
            name="approval_limits",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="approval_currency"),
        CheckConstraint("expires_at > created_at", name="approval_expiry"),
        CheckConstraint("(state = 'pending') = (decided_at IS NULL)", name="approval_decided"),
        CheckConstraint(
            "state NOT IN ('approved', 'denied') OR decision_request_id IS NOT NULL",
            name="approval_decision_request",
        ),
        Index("ix_chat_tool_approval_owner_run", "owner_id", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    input_digest: Mapped[str] = mapped_column(Text, nullable=False)
    provider_key: Mapped[str] = mapped_column(Text, nullable=False)
    config_version: Mapped[str] = mapped_column(Text, nullable=False)
    permission_scope: Mapped[str] = mapped_column(Text, nullable=False)
    max_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    max_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
