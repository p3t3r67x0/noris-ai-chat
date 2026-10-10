"""Database-side seeks and branch windows shared by REST and generation.

Only the selected ancestors are walked; variant metadata is one batch query.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Integer, func, literal, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from noris_ai.chat.cursors import Cursor
from noris_ai.chat.errors import ChatError
from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.chat.schemas import VariantSummary


async def owned(session: AsyncSession, owner: UUID, conversation: UUID) -> ChatConversation:
    row = await session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation,
            ChatConversation.owner_id == owner,
            ChatConversation.deleted_at.is_(None),
        )
    )
    if row is None:
        raise ChatError("NOT_FOUND", 404)
    return row


async def conversation_page(
    session: AsyncSession,
    owner: UUID,
    *,
    limit: int,
    cursor: str | None,
    archived: bool,
    archive_only: bool,
    query: str,
) -> tuple[Sequence[ChatConversation], str | None]:
    scope = f"conversations:{owner}:{archived}:{archive_only}:{query}"
    stmt = select(ChatConversation).where(
        ChatConversation.owner_id == owner,
        ChatConversation.deleted_at.is_(None),
    )
    if archive_only:
        stmt = stmt.where(ChatConversation.archived_at.is_not(None))
    elif not archived:
        stmt = stmt.where(ChatConversation.archived_at.is_(None))
    if query:
        escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(func.lower(ChatConversation.title).like(f"%{escaped}%", escape="\\"))
    if cursor:
        seek = Cursor.decode(cursor, scope)
        if seek.timestamp is None or seek.leaf is not None or seek.revision is not None:
            raise ChatError("INVALID_CURSOR", 422)
        stmt = stmt.where(
            tuple_(ChatConversation.updated_at, ChatConversation.id)
            < tuple_(seek.timestamp, seek.id)
        )
    rows = list(
        (
            await session.scalars(
                stmt.order_by(
                    ChatConversation.updated_at.desc(),
                    ChatConversation.id.desc(),
                ).limit(limit + 1)
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    after = (
        Cursor(scope=scope, id=rows[-1].id, timestamp=rows[-1].updated_at).encode()
        if more
        else None
    )
    return rows, after


async def message_page(
    session: AsyncSession,
    owner: UUID,
    conversation: UUID,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[Sequence[ChatMessage], str | None]:
    await owned(session, owner, conversation)
    scope = f"messages:{owner}:{conversation}"
    stmt = select(ChatMessage).where(ChatMessage.conversation_id == conversation)
    if cursor:
        seek = Cursor.decode(cursor, scope)
        if seek.timestamp is None or seek.leaf is not None or seek.revision is not None:
            raise ChatError("INVALID_CURSOR", 422)
        stmt = stmt.where(
            tuple_(ChatMessage.created_at, ChatMessage.id) < tuple_(seek.timestamp, seek.id)
        )
    rows = list(
        (
            await session.scalars(
                stmt.order_by(
                    ChatMessage.created_at.desc(),
                    ChatMessage.id.desc(),
                ).limit(limit + 1)
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    after = (
        Cursor(scope=scope, id=rows[-1].id, timestamp=rows[-1].created_at).encode()
        if more
        else None
    )
    return list(reversed(rows)), after


async def ancestors(
    session: AsyncSession, conversation: UUID, leaf: UUID | None, limit: int
) -> list[ChatMessage]:
    if leaf is None:
        return []
    seed = (
        select(ChatMessage.id, ChatMessage.parent_message_id, literal(1, Integer).label("depth"))
        .where(
            ChatMessage.conversation_id == conversation,
            ChatMessage.id == leaf,
        )
        .cte("ancestors", recursive=True)
    )
    chain = seed.union_all(
        select(ChatMessage.id, ChatMessage.parent_message_id, seed.c.depth + 1)
        .join(
            seed,
            ChatMessage.id == seed.c.parent_message_id,
        )
        .where(ChatMessage.conversation_id == conversation, seed.c.depth < limit)
    )
    rows = list(
        (
            await session.scalars(
                select(ChatMessage)
                .join(chain, ChatMessage.id == chain.c.id)
                .order_by(chain.c.depth)
            )
        ).all()
    )
    if not rows or len({r.id for r in rows}) != len(rows):
        raise ChatError("INVALID_LEAF", 422)
    return rows  # leaf first


async def full_path(
    session: AsyncSession, conversation: UUID, leaf: UUID | None
) -> list[ChatMessage]:
    rows = await ancestors(session, conversation, leaf, 10_001)
    if rows and rows[-1].parent_message_id is not None:
        # Do not silently truncate authoritative provider context.
        raise ChatError("INVALID_LEAF", 422)
    return list(reversed(rows))


async def branch_leaf(
    session: AsyncSession, conversation: UUID, message: UUID, preferred: UUID | None
) -> UUID:
    if preferred:
        path = await ancestors(session, conversation, preferred, 10_001)
        if any(m.id == message for m in path):
            return preferred
    # A single recursive query, including the latest-child seek at each level.
    stmt = text("""
        WITH RECURSIVE branch AS (
          SELECT id, 1 AS depth FROM chat_message
          WHERE id=:message AND conversation_id=:conversation
          UNION ALL
          SELECT child.id, branch.depth+1 FROM branch
          CROSS JOIN LATERAL (
            SELECT id FROM chat_message
            WHERE conversation_id=:conversation AND parent_message_id=branch.id
            ORDER BY created_at DESC, id DESC LIMIT 1
          ) child WHERE branch.depth < 10001
        ) SELECT id, depth FROM branch ORDER BY depth DESC LIMIT 1
    """)
    result = (
        await session.execute(stmt, {"message": message, "conversation": conversation})
    ).first()
    if result is None or result.depth >= 10_001:
        raise ChatError("INVALID_LEAF", 422)
    return result.id


async def variants(
    session: AsyncSession, conversation: UUID, messages: Sequence[ChatMessage]
) -> list[VariantSummary]:
    if not messages:
        return []
    # Restrict ranking to the selected sibling groups, not the entire tree.
    keys = (
        select(ChatMessage.parent_message_id, ChatMessage.role)
        .where(ChatMessage.id.in_([m.id for m in messages]))
        .distinct()
        .subquery()
    )
    group = [ChatMessage.parent_message_id, ChatMessage.role]
    order = [ChatMessage.created_at, ChatMessage.id]
    ranked = (
        select(
            ChatMessage.id.label("id"),
            func.count().over(partition_by=group).label("total"),
            func.row_number().over(partition_by=group, order_by=order).label("position"),
            func.lag(ChatMessage.id).over(partition_by=group, order_by=order).label("previous"),
            func.lead(ChatMessage.id).over(partition_by=group, order_by=order).label("next"),
        )
        .join(
            keys,
            ChatMessage.parent_message_id.is_not_distinct_from(keys.c.parent_message_id)
            & (ChatMessage.role == keys.c.role),
        )
        .where(ChatMessage.conversation_id == conversation)
        .subquery()
    )
    rows = (
        await session.execute(select(ranked).where(ranked.c.id.in_([m.id for m in messages])))
    ).all()
    return [
        VariantSummary(
            messageId=r.id,
            total=r.total,
            index=r.position,
            previousMessageId=r.previous,
            nextMessageId=r.next,
        )
        for r in rows
    ]


async def path_page(
    session: AsyncSession,
    owner: UUID,
    conversation: UUID,
    *,
    limit: int,
    cursor: str | None,
    message: UUID | None = None,
    preferred: UUID | None = None,
    before: UUID | None = None,
) -> tuple[ChatConversation, UUID | None, list[ChatMessage], list[VariantSummary], str | None]:
    row = await owned(session, owner, conversation)
    scope = f"path:{owner}:{conversation}"
    leaf = (
        await branch_leaf(session, conversation, message, preferred)
        if message
        else row.active_leaf_message_id
    )
    start = leaf
    if cursor or before:
        if before and (cursor or message):
            raise ChatError("INVALID_CURSOR", 422)
        if cursor:
            seek = Cursor.decode(cursor, scope)
        else:
            if before is None:
                raise ChatError("INVALID_CURSOR", 422)
            seek = Cursor(scope=scope, id=before, leaf=leaf)
        if message or seek.timestamp is not None or seek.leaf != leaf:
            raise ChatError("VERSION_CONFLICT", 409)
        # Cursors are not credentials. Verify the boundary belongs to this
        # selected immutable path even if a client constructs its own cursor.
        chain = (
            select(ChatMessage.id, ChatMessage.parent_message_id)
            .where(
                ChatMessage.conversation_id == conversation,
                ChatMessage.id == leaf,
            )
            .cte("boundary_path", recursive=True)
        )
        chain = chain.union(
            select(ChatMessage.id, ChatMessage.parent_message_id)
            .join(
                chain,
                ChatMessage.id == chain.c.parent_message_id,
            )
            .where(ChatMessage.conversation_id == conversation)
        )
        if await session.scalar(select(chain.c.id).where(chain.c.id == seek.id)) is None:
            raise ChatError("INVALID_CURSOR", 422)
        start = seek.id
    rows = await ancestors(session, conversation, start, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    after = (
        Cursor(scope=scope, id=rows[-1].parent_message_id, leaf=leaf, revision=row.version).encode()
        if more and rows[-1].parent_message_id
        else None
    )
    summaries = await variants(session, conversation, rows)
    return row, leaf, list(reversed(rows)), summaries, after
