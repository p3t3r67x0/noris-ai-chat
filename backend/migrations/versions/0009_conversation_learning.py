"""Persist conversation learning mode and abstract reasoning preference."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_conversation_learning"
down_revision: str | None = "0008_pdf_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("conversation_mode", sa.Text(), nullable=False, server_default="normal"),
    )
    op.add_column("chat_conversation", sa.Column("reasoning_preference", sa.Text()))
    op.create_check_constraint(
        "conversation_mode", "chat_conversation", "conversation_mode IN ('normal', 'learning')"
    )
    op.create_check_constraint(
        "reasoning_preference",
        "chat_conversation",
        "reasoning_preference IN ('instant', 'medium', 'high', 'very_high', 'pro')",
    )


def downgrade() -> None:
    op.drop_constraint("reasoning_preference", "chat_conversation", type_="check")
    op.drop_constraint("conversation_mode", "chat_conversation", type_="check")
    op.drop_column("chat_conversation", "reasoning_preference")
    op.drop_column("chat_conversation", "conversation_mode")
