"""Persist conversation pins and index their independent sidebar seek."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_conversation_pinning"
down_revision: str | None = "0011_tool_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_conversation", sa.Column("pinned_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_chat_conversation_pinned_seek",
        "chat_conversation",
        ["owner_id", sa.text("pinned_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text(
            "deleted_at IS NULL AND archived_at IS NULL AND pinned_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_chat_conversation_pinned_seek", table_name="chat_conversation")
    op.drop_column("chat_conversation", "pinned_at")
