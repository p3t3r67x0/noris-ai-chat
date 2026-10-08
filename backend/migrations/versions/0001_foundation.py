"""Establish migration tracking without creating stage-2 domain tables."""

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Alembic itself creates and stamps its version table within a transaction.
    pass


def downgrade() -> None:
    pass
