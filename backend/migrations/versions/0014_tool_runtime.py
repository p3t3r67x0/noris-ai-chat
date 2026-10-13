"""Durable runtime claims and conservative daily reservations (expand only)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014_tool_runtime"
down_revision: str = "0013_conversation_pinning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in (
        sa.Column("reservation_id", sa.Uuid()),
        sa.Column("execution_id", sa.Uuid()),
        sa.Column("execution_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("approval_id", sa.Uuid()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("policy_snapshot", JSONB()),
    ):
        op.add_column("chat_tool_run", column)
    op.create_unique_constraint("uq_chat_tool_run_owner_id", "chat_tool_run", ["owner_id", "id"])
    op.create_check_constraint(
        "tool_policy_size",
        "chat_tool_run",
        "policy_snapshot IS NULL OR (jsonb_typeof(policy_snapshot) = 'object' "
        "AND octet_length(policy_snapshot::text) <= 2048)",
    )
    op.create_check_constraint(
        "tool_dispatch",
        "chat_tool_run",
        "dispatched_at IS NULL OR (execution_id IS NOT NULL AND reservation_id IS NOT NULL)",
    )
    op.create_table(
        "chat_budget_day",
        sa.Column("owner_id", sa.Uuid(), primary_key=True),
        sa.Column("budget_day", sa.Date(), primary_key=True),
        sa.Column("bucket", sa.Text(), primary_key=True),
        sa.Column("currency", sa.Text(), primary_key=True),
        sa.Column("calls", sa.BigInteger(), nullable=False),
        sa.Column("tokens", sa.BigInteger(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("cost", sa.Numeric(20, 8), nullable=False),
        sa.CheckConstraint("bucket IN ('tools', 'text')", name="budget_bucket"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="budget_currency"),
        sa.CheckConstraint(
            "calls >= 0 AND tokens >= 0 AND bytes >= 0 AND cost >= 0 AND cost <> 'NaN'::numeric",
            name="budget_amount",
        ),
    )
    op.create_table(
        "chat_budget_reservation",
        sa.Column("owner_id", sa.Uuid(), primary_key=True),
        sa.Column("bucket", sa.Text(), primary_key=True),
        sa.Column("phase_key", sa.Text(), primary_key=True),
        sa.Column("attempt", sa.BigInteger(), primary_key=True),
        sa.Column("id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("run_id", sa.Uuid()),
        sa.Column("budget_day", sa.Date(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("input_digest", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("calls", sa.BigInteger(), nullable=False),
        sa.Column("tokens", sa.BigInteger(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("measured", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "run_id", "id", name="uq_chat_budget_reservation_owner_run_id"
        ),
        sa.CheckConstraint(
            "bucket <> 'tools' OR run_id IS NOT NULL", name="reservation_tool_scope"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["chat_tool_run.owner_id", "chat_tool_run.id"],
            name="reservation_run",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "budget_day", "bucket", "currency"],
            [
                "chat_budget_day.owner_id",
                "chat_budget_day.budget_day",
                "chat_budget_day.bucket",
                "chat_budget_day.currency",
            ],
            name="reservation_day",
        ),
        sa.CheckConstraint("bucket IN ('tools', 'text')", name="reservation_bucket"),
        sa.CheckConstraint(
            "state IN ('reserved', 'dispatched', 'accounted', 'released', 'unknown')",
            name="reservation_state",
        ),
        sa.CheckConstraint(
            "calls >= 0 AND tokens >= 0 AND bytes >= 0 AND cost >= 0 AND cost <> 'NaN'::numeric",
            name="reservation_amount",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="reservation_currency"),
        sa.CheckConstraint(
            "length(phase_key) BETWEEN 1 AND 200 AND attempt BETWEEN 1 AND 2",
            name="reservation_phase",
        ),
        sa.CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="reservation_digest"),
        sa.CheckConstraint(
            "measured IS NULL OR (jsonb_typeof(measured) = 'object' "
            "AND octet_length(measured::text) <= 1024)",
            name="reservation_measured",
        ),
    )
    op.create_index("ix_chat_budget_reservation_run_id", "chat_budget_reservation", ["run_id"])
    op.create_foreign_key(
        "tool_reservation",
        "chat_tool_run",
        "chat_budget_reservation",
        ["owner_id", "id", "reservation_id"],
        ["owner_id", "run_id", "id"],
    )
    # Match existing role setup; no result UPDATE permission is introduced.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'noris_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON chat_budget_day, chat_budget_reservation TO noris_app;
        END IF; END $$""")


def downgrade() -> None:
    op.drop_constraint("tool_reservation", "chat_tool_run", type_="foreignkey")
    op.drop_table("chat_budget_reservation")
    op.drop_table("chat_budget_day")
    op.drop_constraint(op.f("ck_chat_tool_run_tool_dispatch"), "chat_tool_run", type_="check")
    op.drop_constraint(op.f("ck_chat_tool_run_tool_policy_size"), "chat_tool_run", type_="check")
    op.drop_constraint("uq_chat_tool_run_owner_id", "chat_tool_run", type_="unique")
    for column in (
        "policy_snapshot",
        "dispatched_at",
        "approval_id",
        "execution_deadline_at",
        "execution_id",
        "reservation_id",
    ):
        op.drop_column("chat_tool_run", column)
