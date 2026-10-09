import asyncio
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

# The application requires the chat persistence schema; readiness follows head.
LATEST_REVISION = "0004_chat_continuation"


class ReadinessProbe(Protocol):
    async def is_ready(self) -> bool: ...


class DatabaseReadinessProbe:
    def __init__(self, engine: AsyncEngine, timeout_seconds: float) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds

    async def is_ready(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout_seconds), self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                revisions = (
                    (await connection.execute(text("SELECT version_num FROM alembic_version")))
                    .scalars()
                    .all()
                )
                return list(revisions) == [LATEST_REVISION]
        except (SQLAlchemyError, OSError, TimeoutError):
            # Database exceptions can contain credentials or infrastructure details.
            return False
