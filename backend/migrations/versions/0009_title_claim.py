"""Durable admission for one automatic title call per conversation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_title_claim"
down_revision: str | None = "0008_pdf_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation", sa.Column("title_generation_claimed_at", sa.DateTime(timezone=True))
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "title_generation_claimed_at")
