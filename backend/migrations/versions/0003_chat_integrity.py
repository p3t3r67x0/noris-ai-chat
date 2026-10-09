"""Preserve long responses and enforce immutable message topology.

Revision ID: 0003_chat_integrity
Revises: 0002_chat_persistence
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_chat_integrity"
down_revision: str | None = "0002_chat_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_chat_message_content_length"), "chat_message", type_="check")
    op.create_check_constraint("content_length", "chat_message", "length(content) <= 1048576")
    op.execute("""
    CREATE FUNCTION chat_validate_message() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent_role chat_message_role;
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id
           OR NEW.conversation_id IS DISTINCT FROM OLD.conversation_id
           OR NEW.parent_message_id IS DISTINCT FROM OLD.parent_message_id
           OR NEW.role IS DISTINCT FROM OLD.role
           OR NEW.edited_from_message_id IS DISTINCT FROM OLD.edited_from_message_id
           OR NEW.generation_id IS DISTINCT FROM OLD.generation_id
           OR NEW.model_id IS DISTINCT FROM OLD.model_id
           OR (NEW.content IS DISTINCT FROM OLD.content
               AND (OLD.role = 'user' OR OLD.status NOT IN ('pending', 'streaming'))) THEN
          RAISE EXCEPTION 'immutable message' USING ERRCODE = '23514';
        END IF;
      ELSE
        IF NEW.parent_message_id IS NULL THEN
          IF NEW.role <> 'user' THEN
            RAISE EXCEPTION 'invalid root role' USING ERRCODE = '23514';
          END IF;
        ELSE
          SELECT role INTO parent_role FROM chat_message
          WHERE id = NEW.parent_message_id AND conversation_id = NEW.conversation_id;
          IF parent_role IS NULL OR parent_role = NEW.role THEN
            RAISE EXCEPTION 'invalid parent' USING ERRCODE = '23514';
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER chat_message_integrity BEFORE INSERT OR UPDATE ON chat_message
      FOR EACH ROW EXECUTE FUNCTION chat_validate_message();
    """)


def downgrade() -> None:
    # Does not truncate long responses. A rollback retaining stage-2 rows is safe.
    op.execute("DROP TRIGGER chat_message_integrity ON chat_message")
    op.execute("DROP FUNCTION chat_validate_message()")
    op.drop_constraint(op.f("ck_chat_message_content_length"), "chat_message", type_="check")
    op.create_check_constraint(
        "content_length", "chat_message", "length(content) <= 128000", postgresql_not_valid=True
    )
