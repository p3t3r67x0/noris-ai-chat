"""Add typed tool runs results and approvals

Revision ID: 0011_tool_foundation
Revises: 0010_conversation_learning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_tool_foundation"
down_revision: str | None = "0010_conversation_learning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expand only: legacy rows/columns and generation states remain untouched.
    op.create_unique_constraint(
        "uq_chat_conversation_owner_id", "chat_conversation", ["owner_id", "id"]
    )
    op.create_unique_constraint(
        "uq_chat_generation_owner_conversation_id",
        "chat_generation",
        ["owner_id", "conversation_id", "id"],
    )
    op.create_table(
        "chat_tool_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("tool_id", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("invocation_kind", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_digest", sa.Text(), nullable=False),
        sa.Column("provider_key", sa.Text(), nullable=True),
        sa.Column("config_version", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state IN ('queued', 'awaiting_approval', 'running')) = (finished_at IS NULL)",
            name=op.f("ck_chat_tool_run_tool_finished"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_chat_tool_run_tool_input_digest")
        ),
        sa.CheckConstraint(
            "invocation_kind IN ('web_mode', 'research_step', 'user_action')",
            name=op.f("ck_chat_tool_run_tool_invocation"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(input) = 'object' AND octet_length(input::text) <= 65536",
            name=op.f("ck_chat_tool_run_tool_input_size"),
        ),
        sa.CheckConstraint(
            "state <> 'running' OR started_at IS NOT NULL",
            name=op.f("ck_chat_tool_run_tool_started"),
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'awaiting_approval', 'running', 'succeeded', 'failed',"
            " 'cancelled', 'timed_out', 'interrupted', 'outcome_unknown')",
            name=op.f("ck_chat_tool_run_tool_state"),
        ),
        sa.CheckConstraint(
            "tool_id ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+\\.v[1-9][0-9]*$'"
            " AND length(tool_id) <= 100",
            name=op.f("ck_chat_tool_run_tool_id"),
        ),
        sa.CheckConstraint(
            "(provider_key IS NULL) = (config_version IS NULL)",
            name=op.f("ck_chat_tool_run_tool_provider_pair"),
        ),
        sa.CheckConstraint(
            "length(error_code) BETWEEN 1 AND 100", name=op.f("ck_chat_tool_run_tool_error_size")
        ),
        sa.CheckConstraint(
            "length(provider_key) BETWEEN 1 AND 100 AND length(config_version) BETWEEN 1 AND 100",
            name=op.f("ck_chat_tool_run_tool_provider_size"),
        ),
        sa.CheckConstraint(
            "length(step_key) BETWEEN 1 AND 100", name=op.f("ck_chat_tool_run_tool_step_key")
        ),
        sa.CheckConstraint(
            "parent_run_id IS NULL OR parent_run_id <> id",
            name=op.f("ck_chat_tool_run_tool_parent_not_self"),
        ),
        sa.CheckConstraint(
            "schema_version >= 1 AND attempt >= 1", name=op.f("ck_chat_tool_run_tool_versions")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "conversation_id", "generation_id", "parent_run_id"],
            [
                "chat_tool_run.owner_id",
                "chat_tool_run.conversation_id",
                "chat_tool_run.generation_id",
                "chat_tool_run.id",
            ],
            name="tool_parent",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "conversation_id", "generation_id"],
            ["chat_generation.owner_id", "chat_generation.conversation_id", "chat_generation.id"],
            name="tool_generation",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "conversation_id"],
            ["chat_conversation.owner_id", "chat_conversation.id"],
            name="tool_conversation",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_tool_run")),
        sa.UniqueConstraint("generation_id", "step_key", name="uq_chat_tool_run_step"),
        sa.UniqueConstraint(
            "id", "provider_key", "config_version", name="uq_chat_tool_run_provider"
        ),
        sa.UniqueConstraint(
            "owner_id", "conversation_id", "generation_id", "id", name="uq_chat_tool_run_scope"
        ),
        sa.UniqueConstraint("owner_id", "id", "input_digest", name="uq_chat_tool_run_input"),
    )
    op.create_index(
        "ix_chat_tool_run_owner_generation",
        "chat_tool_run",
        ["owner_id", "generation_id"],
        unique=False,
    )
    op.create_index(
        "ix_chat_tool_run_state_deadline", "chat_tool_run", ["state", "deadline_at"], unique=False
    )
    op.create_table(
        "chat_tool_approval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("input_digest", sa.Text(), nullable=False),
        sa.Column("provider_key", sa.Text(), nullable=False),
        sa.Column("config_version", sa.Text(), nullable=False),
        sa.Column("permission_scope", sa.Text(), nullable=False),
        sa.Column("max_calls", sa.Integer(), nullable=False),
        sa.Column("max_cost", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_request_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'pending') = (decided_at IS NULL)",
            name=op.f("ck_chat_tool_approval_approval_decided"),
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_chat_tool_approval_approval_currency")
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_chat_tool_approval_approval_digest")
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'denied', 'expired')",
            name=op.f("ck_chat_tool_approval_approval_state"),
        ),
        sa.CheckConstraint(
            "state NOT IN ('approved', 'denied') OR decision_request_id IS NOT NULL",
            name=op.f("ck_chat_tool_approval_approval_decision_request"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_chat_tool_approval_approval_expiry")
        ),
        sa.CheckConstraint(
            "length(permission_scope) BETWEEN 1 AND 200",
            name=op.f("ck_chat_tool_approval_approval_scope"),
        ),
        sa.CheckConstraint(
            "max_calls >= 1 AND max_cost >= 0 AND max_cost <> 'NaN'::numeric",
            name=op.f("ck_chat_tool_approval_approval_limits"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "run_id", "input_digest"],
            ["chat_tool_run.owner_id", "chat_tool_run.id", "chat_tool_run.input_digest"],
            name="approval_input",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "provider_key", "config_version"],
            ["chat_tool_run.id", "chat_tool_run.provider_key", "chat_tool_run.config_version"],
            name="approval_provider",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_tool_approval")),
        sa.UniqueConstraint("decision_request_id", name="uq_chat_tool_approval_decision"),
    )
    op.create_index(
        "ix_chat_tool_approval_owner_run",
        "chat_tool_approval",
        ["owner_id", "run_id"],
        unique=False,
    )
    op.create_table(
        "chat_tool_result",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=False),
        sa.Column("output_schema", sa.Text(), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_digest", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(output) = 'object' AND octet_length(output::text) <= 262144",
            name=op.f("ck_chat_tool_result_tool_output_size"),
        ),
        sa.CheckConstraint(
            "result_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_chat_tool_result_tool_result_digest")
        ),
        sa.CheckConstraint(
            "length(output_schema) BETWEEN 1 AND 100",
            name=op.f("ck_chat_tool_result_tool_output_schema"),
        ),
        sa.CheckConstraint(
            "result_version >= 1", name=op.f("ck_chat_tool_result_tool_result_version")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["chat_tool_run.id"], name=op.f("fk_chat_tool_result_run_id_chat_tool_run")
        ),
        sa.PrimaryKeyConstraint("run_id", "result_version", name=op.f("pk_chat_tool_result")),
    )

    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'noris_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
          chat_tool_run, chat_tool_approval TO noris_app;
        GRANT SELECT, INSERT, DELETE ON TABLE chat_tool_result TO noris_app;
      END IF;
    END $$;
    """)


def downgrade() -> None:
    # Destructive for tool data; only disposable tests or explicit restore workflows.
    op.drop_table("chat_tool_result")
    op.drop_index("ix_chat_tool_approval_owner_run", table_name="chat_tool_approval")
    op.drop_table("chat_tool_approval")
    op.drop_index("ix_chat_tool_run_state_deadline", table_name="chat_tool_run")
    op.drop_index("ix_chat_tool_run_owner_generation", table_name="chat_tool_run")
    op.drop_table("chat_tool_run")
    op.drop_constraint(
        "uq_chat_generation_owner_conversation_id", "chat_generation", type_="unique"
    )
    op.drop_constraint("uq_chat_conversation_owner_id", "chat_conversation", type_="unique")
