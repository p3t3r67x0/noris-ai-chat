"""Actual authenticated search API + captured EXPLAIN plans on synthetic data.

Only loopback databases named noris_search_benchmark_*_test are accepted.
Never reads operator .env files, calls providers or touches an application DB.
"""

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import Table, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.schema import CreateIndex

from noris_ai.chat.models import ChatConversation, ChatMessage
from noris_ai.core.config import Settings
from noris_ai.main import create_app

OWNER = UUID(int=42)
INDEX_NAMES = {"ix_chat_conversation_search_unicode", "ix_chat_message_search_unicode"}
CASES = {
    "rare_message": {"q": "unique_7429"},
    "split_terms_and_phrase_rank": {"q": "docker healthcheck"},
    "split_terms_page_2": {"q": "docker healthcheck"},
    "unicode": {"q": "STRASSE ÄPFEL"},
    "no_match": {"q": "unfindable-noris-marker"},
    "literal_symbols": {"q": "%_"},
    "short_term": {"q": "a"},
    "common_term": {"q": "synthetic"},
    "common_phrase": {"q": "synthetic note"},
    "common_distributed_terms": {"q": "synthetic operations"},
    "common_distributed_page_2": {"q": "synthetic operations"},
    "combined_filters": {"q": "docker healthcheck", "archiveFilter": "archived", "pinned": "false"},
    "filters_only": {"archiveFilter": "all", "pinned": "true"},
}


def require_benchmark_database(url: str) -> None:
    parsed = make_url(url)
    name = parsed.database or ""
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host not in ("127.0.0.1", "localhost", "::1")
        or not name.startswith("noris_search_benchmark_")
        or not name.endswith("_test")
    ):
        raise ValueError("Use a dedicated loopback noris_search_benchmark_*_test database")


async def seed(engine: AsyncEngine, count: int, reuse: bool) -> None:
    async with engine.begin() as connection:
        conversations = await connection.scalar(text("SELECT count(*) FROM chat_conversation"))
        if conversations:
            foreign = await connection.scalar(
                text(
                    "SELECT count(*) FROM chat_conversation "
                    "WHERE title NOT LIKE 'Search benchmark %'"
                )
            )
            messages = await connection.scalar(text("SELECT count(*) FROM chat_message"))
            if not reuse or foreign or conversations != count or messages != count * 10:
                raise ValueError(
                    "Seed requires an empty database, or the identical --reuse-seed dataset"
                )
            return
        await connection.execute(
            text("""
            INSERT INTO chat_conversation
              (id,owner_id,title,title_source,version,updated_at,archived_at,pinned_at,deleted_at)
            SELECT md5('search-a1-conversation-'||i)::uuid,
                   CASE WHEN i%10=0 THEN md5('foreign-owner')::uuid ELSE :owner END,
                   'Search benchmark '||i||CASE WHEN i%25=0 THEN ' Docker' ELSE '' END||
                     CASE WHEN i%101=0 THEN ' Straße' ELSE '' END,
                   'manual',1,timestamptz '2026-01-01' + i * interval '1 second',
                   CASE WHEN i%7=0 THEN timestamptz '2026-02-01' END,
                   CASE WHEN i%11=0 THEN timestamptz '2026-02-02' END,
                   CASE WHEN i%503=0 THEN timestamptz '2026-02-03' END
            FROM generate_series(1,:count) i
        """),
            {"count": count, "owner": OWNER},
        )
        await connection.execute(
            text("""
            INSERT INTO chat_message
              (id,conversation_id,parent_message_id,role,content,status,created_at)
            SELECT md5('search-a1-message-'||c||'-'||m)::uuid,
                   md5('search-a1-conversation-'||c)::uuid,
                   CASE WHEN m=1 THEN NULL ELSE md5('search-a1-message-'||c||'-'||(m-1))::uuid END,
                   CASE WHEN m%2=1 THEN 'user'::chat_message_role
                        ELSE 'assistant'::chat_message_role END,
                   'Synthetic note '||c||'/'||m||' '||
                     repeat('Useful deterministic text about testing and operations. ',5)||
                     CASE WHEN m=4 AND c%25=0 THEN ' healthcheck' ELSE '' END||
                     CASE WHEN m=6 AND c%125=0 THEN ' docker healthcheck' ELSE '' END||
                     CASE WHEN m=2 AND c%101=0 THEN ' A' || chr(776) || 'pfel' ELSE '' END||
                     CASE WHEN m=8 THEN ' unique_'||c ELSE '' END||
                     CASE WHEN m=10 AND c%37=0 THEN ' literal %_' ELSE '' END,
                   'completed',timestamptz '2026-01-01' + m * interval '1 second'
            FROM generate_series(1,:count) c, generate_series(1,10) m ORDER BY c,m
        """),
            {"count": count},
        )
        await connection.execute(text("ANALYZE chat_conversation"))
        await connection.execute(text("ANALYZE chat_message"))


async def indexes(engine: AsyncEngine, *, enabled: bool) -> None:
    async with engine.connect() as base:
        connection = await base.execution_options(isolation_level="AUTOCOMMIT")
        for model in (ChatConversation, ChatMessage):
            table = cast(Table, model.__table__)
            for index in table.indexes:
                if index.name in INDEX_NAMES:
                    if enabled:
                        sql = str(
                            CreateIndex(index, if_not_exists=True).compile(dialect=engine.dialect)
                        )
                    else:
                        # Identifiers are the fixed model index names, never CLI/query data.
                        sql = f"DROP INDEX IF EXISTS {index.name}"
                    await connection.execute(text(sql))
        await connection.execute(text("ANALYZE chat_conversation"))
        await connection.execute(text("ANALYZE chat_message"))


async def measure(url: str, repetitions: int) -> dict[str, Any]:
    password = SecretStr("fixture-application-password-never-real")
    config = Settings(
        environment="test",
        database_url=SecretStr(url),
        chat_owner_id=OWNER,
        llm_provider="disabled",
        llm_models=(),
        llm_access_username="fixture-user",
        llm_access_password=password,
    )
    app = create_app(settings=config)
    result: dict[str, Any] = {}
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            auth=(config.llm_access_username, password.get_secret_value()),
        ) as client,
    ):
        engine: AsyncEngine = app.state.chat_database.kw["bind"]
        statements: list[tuple[str, Any]] = []

        def capture(
            _connection: Any,
            _cursor: Any,
            statement: str,
            parameters: Any,
            _context: Any,
            _many: bool,
        ) -> None:
            if statement.startswith("SELECT") and (
                "chat_conversation.title" in statement or "chat_message.content" in statement
            ):
                statements.append((statement, parameters))

        for label, params in CASES.items():
            params = dict(params)
            if label.endswith("_page_2"):
                first = await client.get("/api/v1/conversations", params=params)
                first.raise_for_status()
                cursor = first.json().get("nextCursor")
                if not cursor:
                    raise ValueError("Benchmark fixture must provide a second result page")
                params["cursor"] = str(cursor)
            # One warm-up; API timings include DB access, snippets and JSON serialization.
            response = await client.get("/api/v1/conversations", params=params)
            response.raise_for_status()
            times: list[float] = []
            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                for _ in range(repetitions):
                    statements.clear()
                    started = time.perf_counter()
                    response = await client.get("/api/v1/conversations", params=params)
                    response.raise_for_status()
                    times.append((time.perf_counter() - started) * 1000)
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)
            plans: list[Any] = []
            async with engine.connect() as connection:
                for sql, parameters in statements:
                    # Prefix only: original SQL and its original bound parameters are preserved.
                    rows = await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, parameters
                    )
                    plans.append(rows.scalar_one()[0])
            data = response.json()
            result[label] = {
                "params": params,
                "samples": repetitions,
                "times_ms": [round(value, 3) for value in times],
                "p50_ms": round(statistics.median(times), 3),
                "p95_ms": round(sorted(times)[math.ceil(len(times) * 0.95) - 1], 3),
                "returned": len(data["conversations"]),
                "snippets": len(data.get("matches", [])),
                "response_bytes": len(response.content),
                "plans": plans,
            }
            print(label, result[label]["p95_ms"], "ms", flush=True)
            statements.clear()
    return result


async def run(args: argparse.Namespace) -> None:
    require_benchmark_database(args.database_url)
    if (
        args.conversations < 7500
        or not 3 <= args.repetitions <= 100
        or not 3 <= args.baseline_repetitions <= 100
    ):
        raise ValueError("Use >=7500 conversations and 3-100 repetitions")
    engine = create_async_engine(args.database_url)
    seeded = False
    try:
        await seed(engine, args.conversations, args.reuse_seed)
        seeded = True
        async with engine.connect() as connection:
            version = await connection.scalar(text("SELECT version()"))
            settings = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT name, setting FROM pg_settings WHERE name IN "
                            "('shared_buffers','work_mem','effective_cache_size','jit',"
                            "'max_parallel_workers_per_gather','server_encoding')"
                        )
                    )
                ).all()
            )
        cpuinfo = await asyncio.to_thread(Path("/proc/cpuinfo").read_text)
        cpu = next(
            (
                line.partition(":")[2].strip()
                for line in cpuinfo.splitlines()
                if line.startswith("model name")
            ),
            platform.machine(),
        )
        result = {
            "postgresql": version,
            "postgresql_settings": settings,
            "dataset_version": "a1-v1-phrase-every-125",
            "python": platform.python_version(),
            "cpu": cpu,
            "logical_cpus": os.cpu_count(),
            "machine": platform.machine(),
            "memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            "conversations": args.conversations,
            "messages": args.conversations * 10,
            "method": (
                "single client; one warm-up; authenticated ASGI API incl. DB/snippets/JSON; "
                "P95 nearest rank; all timings ms"
            ),
        }
        if args.compare_indexes:
            await indexes(engine, enabled=False)
            result["without_unicode_indexes"] = await measure(
                args.database_url, args.baseline_repetitions
            )
        await indexes(engine, enabled=True)
        result["with_unicode_indexes"] = await measure(args.database_url, args.repetitions)
        async with engine.connect() as connection:
            result["index_bytes"] = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT c.relname, pg_relation_size(c.oid) FROM pg_class c "
                            "WHERE c.relname IN "
                            "('ix_chat_message_search_unicode','ix_chat_conversation_search_unicode')"
                        )
                    )
                ).all()
            )
        await asyncio.to_thread(
            args.output.write_text,
            json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
        )
    finally:
        # Even failed comparisons leave the head schema's indexes in place.
        if seeded and args.compare_indexes:
            await indexes(engine, enabled=True)
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conversations", type=int, default=10_000)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--baseline-repetitions", type=int, default=3)
    parser.add_argument("--compare-indexes", action="store_true")
    parser.add_argument("--reuse-seed", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
