"""Persist the existing answer-continuation semantics without replacing variants.

Revision ID: 0004_chat_continuation
Revises: 0003_chat_integrity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chat_continuation"
down_revision: str | None = "0003_chat_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE chat_message_status ADD VALUE IF NOT EXISTS 'incomplete'")
    op.execute("ALTER TYPE chat_generation_status ADD VALUE IF NOT EXISTS 'incomplete'")
    op.add_column(
        "chat_message",
        sa.Column("continuation_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("chat_message", sa.Column("error_code", sa.Text()))
    op.add_column("chat_message", sa.Column("error_message", sa.Text()))
    op.add_column(
        "chat_generation",
        sa.Column("operation", sa.Text(), nullable=False, server_default="generate"),
    )
    op.add_column("chat_generation", sa.Column("source_message_id", sa.Uuid()))
    op.create_foreign_key(
        "source_message",
        "chat_generation",
        "chat_message",
        ["conversation_id", "source_message_id"],
        ["conversation_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("source_message", "chat_generation", type_="foreignkey")
    op.drop_column("chat_generation", "source_message_id")
    op.drop_column("chat_generation", "operation")
    op.drop_column("chat_message", "error_message")
    op.drop_column("chat_message", "error_code")
    op.drop_column("chat_message", "continuation_count")
    # PostgreSQL enum labels remain, preserving existing incomplete answer data.
