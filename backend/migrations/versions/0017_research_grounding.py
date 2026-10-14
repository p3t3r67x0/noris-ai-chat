"""Bounded internal research projection on the existing generation.

Revision ID: 0017_research_grounding
Revises: 0016_source_fetch
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017_research_grounding"
down_revision = "0016_source_fetch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_generation", sa.Column("research", JSONB(none_as_null=True), nullable=True))
    op.create_check_constraint(
        "research_bound",
        "chat_generation",
        "research IS NULL OR (jsonb_typeof(research) = 'object' "
        "AND octet_length(research::text) <= 131072)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_chat_generation_research_bound"), "chat_generation", type_="check")
    op.drop_column("chat_generation", "research")
