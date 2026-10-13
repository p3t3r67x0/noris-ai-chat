"""Tool projection sequence; reuse the existing chat event outbox.

Revision ID: 0015_tool_events
Revises: 0014_tool_runtime
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_tool_events"
down_revision = "0014_tool_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy runs reconstruct directly from durable state, at sequence zero.
    op.add_column(
        "chat_tool_run",
        sa.Column("event_sequence", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint("tool_event_sequence", "chat_tool_run", "event_sequence >= 0")
    op.add_column("chat_tool_run", sa.Column("event_updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("chat_tool_run", "event_updated_at")
    op.drop_constraint(op.f("ck_chat_tool_run_tool_event_sequence"), "chat_tool_run", type_="check")
    op.drop_column("chat_tool_run", "event_sequence")
