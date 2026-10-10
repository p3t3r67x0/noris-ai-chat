"""Non-destructive seek and sibling indexes.

Revision ID: 0005_chat_pagination
Revises: 0004_chat_continuation
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_chat_pagination"
down_revision: str | None = "0004_chat_continuation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = {
    "ix_chat_conversation_seek": (
        "ON chat_conversation (owner_id, updated_at DESC, id DESC) WHERE deleted_at IS NULL"
    ),
    "ix_chat_conversation_active_seek": (
        "ON chat_conversation (owner_id, updated_at DESC, id DESC) "
        "WHERE deleted_at IS NULL AND archived_at IS NULL"
    ),
    "ix_chat_message_seek": "ON chat_message (conversation_id, created_at DESC, id DESC)",
    "ix_chat_message_siblings": (
        "ON chat_message (conversation_id, parent_message_id, role, created_at, id)"
    ),
    "ix_chat_conversation_title_search": (
        "ON chat_conversation USING gin (lower(title) gin_trgm_ops) WHERE deleted_at IS NULL"
    ),
}


def upgrade() -> None:
    # pg_trgm is a trusted extension. The migration role needs CREATE on this DB.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        for name, definition in INDEXES.items():
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} {definition}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in reversed(INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    # Retain pg_trgm: other applications/indexes may use the extension.
