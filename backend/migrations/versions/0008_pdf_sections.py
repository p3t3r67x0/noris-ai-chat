"""Preserve page-referenced PDF sections in the existing attachment system."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008_pdf_sections"
down_revision: str | None = "0007_text_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_attachment", sa.Column("pdf_sections", JSONB()))
    op.add_column("chat_attachment", sa.Column("pdf_page_count", sa.Integer()))
    op.create_check_constraint(
        "attachment_pdf_pages", "chat_attachment", "pdf_page_count BETWEEN 1 AND 100"
    )
    op.create_check_constraint(
        "attachment_pdf_sections",
        "chat_attachment",
        "pdf_sections IS NULL OR (mime_type = 'application/pdf' AND pdf_page_count IS NOT NULL"
        " AND jsonb_typeof(pdf_sections) = 'array' AND jsonb_array_length(pdf_sections) <= 600)",
    )


def downgrade() -> None:
    op.drop_constraint("attachment_pdf_sections", "chat_attachment", type_="check")
    op.drop_constraint("attachment_pdf_pages", "chat_attachment", type_="check")
    op.drop_column("chat_attachment", "pdf_page_count")
    op.drop_column("chat_attachment", "pdf_sections")
