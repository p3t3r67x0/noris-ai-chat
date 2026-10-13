"""Keep prepared conversations out of the sidebar without hiding legacy chats."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_conversation_visibility"
down_revision: str | None = "0011_tool_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation",
        sa.Column("sidebar_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("chat_conversation", "sidebar_visible")
