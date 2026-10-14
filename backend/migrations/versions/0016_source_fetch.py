"""Normalized fetch provenance; preserve existing runs and results.

Revision ID: 0016_source_fetch
Revises: 0015_tool_events
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_source_fetch"
down_revision = "0015_tool_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_tool_run", sa.Column("source_search_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "tool_source_search",
        "chat_tool_run",
        "chat_tool_run",
        ["owner_id", "conversation_id", "generation_id", "source_search_run_id"],
        ["owner_id", "conversation_id", "generation_id", "id"],
    )
    op.create_check_constraint(
        "tool_source_search_binding",
        "chat_tool_run",
        "source_search_run_id IS NULL OR (tool_id = 'web.fetch.v1' AND source_search_run_id <> id)",
    )


def downgrade() -> None:
    # Removes provenance only. All existing ToolResult bodies and chat rows survive.
    op.drop_constraint(
        op.f("ck_chat_tool_run_tool_source_search_binding"), "chat_tool_run", type_="check"
    )
    op.drop_constraint("tool_source_search", "chat_tool_run", type_="foreignkey")
    op.drop_column("chat_tool_run", "source_search_run_id")
