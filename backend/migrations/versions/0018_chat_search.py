"""Unicode literal substring indexes; no chat data or topology is rewritten.

Concurrent builds avoid blocking chat writes. Interrupted builds are retryable.
Requires the existing UTF8 PostgreSQL 18 / pg_trgm deployment contract.
"""

from alembic import op
from sqlalchemy import text

revision = "0018_chat_search"
down_revision = "0017_research_grounding"
branch_labels = None
depends_on = None

INDEXES = {
    "ix_chat_conversation_search_unicode": (
        "ON chat_conversation USING gin ((CASE WHEN char_length(title)=octet_length(title) "
        'THEN lower(title COLLATE "C") ELSE normalize(casefold(normalize(title) '
        'COLLATE "pg_unicode_fast")) COLLATE "C" END) gin_trgm_ops) WHERE deleted_at IS NULL'
    ),
    "ix_chat_message_search_unicode": (
        "ON chat_message USING gin ((CASE WHEN char_length(content)=octet_length(content) "
        'THEN lower(content COLLATE "C") ELSE normalize(casefold(normalize(content) '
        'COLLATE "pg_unicode_fast")) COLLATE "C" END) gin_trgm_ops)'
    ),
}


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, definition in INDEXES.items():
            invalid = op.get_bind().scalar(
                text(
                    "SELECT NOT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                    "WHERE c.relname=:name AND c.relnamespace='public'::regnamespace"
                ),
                {"name": name},
            )
            if invalid:
                op.execute(f"DROP INDEX CONCURRENTLY {name}")
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} {definition}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in reversed(INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
