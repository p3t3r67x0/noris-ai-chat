"""Merge the published pinning and visibility revisions without repeating DDL.

Keep this head ID for databases that already applied the former linear 0013
pinning migration: they already contain both branches' columns and indexes.
"""

from collections.abc import Sequence

revision: str = "0013_conversation_pinning"
down_revision: tuple[str, str] = ("0012_conversation_visibility", "0012_conversation_pinning")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
