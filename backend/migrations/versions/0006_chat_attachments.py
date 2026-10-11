"""Private attachment metadata; existing conversations and messages are retained."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_chat_attachments"
down_revision: str | None = "0005_chat_pagination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_attachment",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "conversation_id", sa.Uuid(), sa.ForeignKey("chat_conversation.id"), nullable=False
        ),
        sa.Column("message_id", sa.Uuid()),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "message_id"],
            ["chat_message.conversation_id", "chat_message.id"],
            name="attachment_message",
        ),
        sa.UniqueConstraint("storage_key", name="uq_chat_attachment_storage_key"),
        sa.CheckConstraint("size_bytes > 0", name="attachment_size"),
        sa.CheckConstraint("status IN ('ready', 'stored', 'deleted')", name="attachment_status"),
    )
    op.create_index(
        "ix_chat_attachment_owner_created", "chat_attachment", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_chat_attachment_conversation_message",
        "chat_attachment",
        ["conversation_id", "message_id"],
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'noris_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE chat_attachment TO noris_app;
      END IF;
    END $$;""")


def downgrade() -> None:
    op.drop_table("chat_attachment")
