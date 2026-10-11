"""Extend existing attachments with immutable text snapshot provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_text_references"
down_revision: str | None = "0006_chat_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_attachment", sa.Column("source_message_id", sa.Uuid()))
    op.add_column("chat_attachment", sa.Column("source_conversation_id", sa.Uuid()))
    op.create_check_constraint(
        "attachment_reference_source",
        "chat_attachment",
        "(source_message_id IS NULL) = (source_conversation_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("attachment_reference_source", "chat_attachment", type_="check")
    op.drop_column("chat_attachment", "source_conversation_id")
    op.drop_column("chat_attachment", "source_message_id")
