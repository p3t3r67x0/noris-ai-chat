"""Reproducible synthetic seed and API/EXPLAIN measurements. No provider calls.

Requires a dedicated empty *_test database migrated to head. Appends scenarios
of 100, 1,000 and 10,000 conversations; it never deletes any data.
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

OWNER = uuid.UUID(int=42)
AUTH = ("fixture-user", "fixture-application-password-never-real")


async def seed(url: str, count: int) -> None:
    if not (make_url(url).database or "").endswith("_test"):
        raise ValueError("Use a dedicated *_test database")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        foreign = await connection.scalar(
            text(
                "SELECT count(*) FROM chat_conversation"
                " WHERE title NOT LIKE 'Pagination benchmark %'"
            )
        )
        if foreign:
            raise ValueError("Benchmark database contains other data; refusing to write")
        await connection.execute(
            text("""
          INSERT INTO chat_conversation (id, owner_id, title, title_source, version, updated_at)
          SELECT md5('pagination-conversation-'||i)::uuid, :owner,
                 'Pagination benchmark '||i, 'manual', 1,
                 timestamptz '2026-01-01' + i * interval '1 second'
          FROM generate_series(1, :count) i ON CONFLICT (id) DO NOTHING
        """),
            {"owner": OWNER, "count": count},
        )
        # Parents are ordered before children. 1 long conversation, 10 medium,
        # all remaining conversations have 10 messages. Content is synthetic.
        await connection.execute(
            text("""
          INSERT INTO chat_message (id, conversation_id, parent_message_id, role,
                                    content, status, created_at)
          SELECT md5('pagination-message-'||c||'-'||m)::uuid,
                 md5('pagination-conversation-'||c)::uuid,
                 CASE WHEN m=1 THEN NULL ELSE md5('pagination-message-'||c||'-'||(m-1))::uuid END,
                 CASE WHEN m%2=1 THEN 'user'::chat_message_role
                      ELSE 'assistant'::chat_message_role END,
                 'Synthetic '||c||'/'||m||' '||repeat('text ', 25), 'completed',
                 timestamptz '2026-01-01' + m * interval '1 millisecond'
          FROM generate_series(1, :count) c,
               LATERAL generate_series(1, CASE WHEN c=1 THEN 1000 WHEN c<=11 THEN 100 ELSE 10 END) m
          ORDER BY c,m ON CONFLICT (id) DO NOTHING
        """),
            {"count": count},
        )
        await connection.execute(
            text("""
          UPDATE chat_conversation c SET active_leaf_message_id=m.id FROM (
            SELECT DISTINCT ON (conversation_id) conversation_id,id FROM chat_message
            ORDER BY conversation_id,created_at DESC,id DESC
          ) m WHERE c.id=m.conversation_id AND c.owner_id=:owner
        """),
            {"owner": OWNER},
        )
        await connection.execute(
            text("""
          INSERT INTO chat_user_preferences (owner_id,active_conversation_id)
          VALUES (:owner, md5('pagination-conversation-1')::uuid)
          ON CONFLICT(owner_id) DO UPDATE SET active_conversation_id=EXCLUDED.active_conversation_id
        """),
            {"owner": OWNER},
        )
        await connection.execute(text("ANALYZE chat_conversation"))
        await connection.execute(text("ANALYZE chat_message"))
    await engine.dispose()


async def measure(url: str, base: str, repetitions: int, legacy: bool = False) -> dict[str, Any]:
    active = uuid.UUID(
        hex=hashlib.md5(b"pagination-conversation-1", usedforsecurity=False).hexdigest()
    )
    results: dict[str, Any] = {}
    resource = "messages" if legacy else "active-path"
    async with httpx.AsyncClient(base_url=base, auth=AUTH) as client:
        for label, path in {
            "conversation_page": "/api/v1/conversations?limit=50",
            "active_window": f"/api/v1/conversations/{active}/{resource}",
            "search": "/api/v1/conversations?q=benchmark%209999",
        }.items():
            if legacy and label == "search":
                results[label] = {"status": "NOT SUPPORTED: legacy search was browser-local"}
                continue
            times: list[float] = []
            size = 0
            for _ in range(repetitions):
                started = time.perf_counter()
                response = await client.get(path)
                response.raise_for_status()
                size = len(response.content)
                times.append((time.perf_counter() - started) * 1000)
            results[label] = {
                "p50_ms": round(statistics.median(times), 3),
                "p95_ms": round(sorted(times)[int((len(times) - 1) * 0.95)], 3),
                "response_bytes": size,
                "samples": repetitions,
            }
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        plans = {}
        for name, sql, parameters in [
            (
                "sidebar",
                "SELECT * FROM chat_conversation WHERE owner_id=:owner"
                " AND deleted_at IS NULL AND archived_at IS NULL"
                " ORDER BY updated_at DESC,id DESC LIMIT 51",
                {"owner": OWNER},
            ),
            (
                "message_page",
                "SELECT * FROM chat_message WHERE conversation_id=:conversation"
                " ORDER BY created_at DESC,id DESC LIMIT 51",
                {"conversation": active},
            ),
            (
                "search",
                "SELECT * FROM chat_conversation WHERE owner_id=:owner AND deleted_at IS NULL"
                " AND lower(title) LIKE '%benchmark 9999%'"
                " ORDER BY updated_at DESC,id DESC LIMIT 51",
                {"owner": OWNER},
            ),
            (
                "active_ancestors",
                "WITH RECURSIVE path AS ("
                " SELECT id,parent_message_id,1 AS depth FROM chat_message"
                " WHERE conversation_id=:conversation AND id=:leaf UNION ALL"
                " SELECT m.id,m.parent_message_id,path.depth+1 FROM chat_message m"
                " JOIN path ON m.id=path.parent_message_id"
                " WHERE m.conversation_id=:conversation AND path.depth<51)"
                " SELECT m.* FROM chat_message m JOIN path ON m.id=path.id ORDER BY path.depth",
                {
                    "conversation": active,
                    "leaf": uuid.UUID(
                        hex=hashlib.md5(
                            b"pagination-message-1-1000",
                            usedforsecurity=False,
                        ).hexdigest()
                    ),
                },
            ),
        ]:
            plans[name] = (
                await connection.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql), parameters
                )
            ).scalar_one()
        results["plans"] = plans
        results["message_count"] = await connection.scalar(
            text("SELECT count(*) FROM chat_message")
        )
        results["postgresql"] = await connection.scalar(text("SELECT version()"))
    await engine.dispose()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--count", type=int, choices=[100, 1000, 10000], required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8596")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--measure-only", action="store_true")
    args = parser.parse_args()
    if not args.measure_only:
        asyncio.run(seed(args.database_url, args.count))
    if args.output:
        result = asyncio.run(measure(args.database_url, args.base_url, args.samples, args.legacy))
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
