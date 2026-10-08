from typing import cast
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from noris_ai.db.readiness import DatabaseReadinessProbe


async def test_database_errors_return_unavailable_without_raising() -> None:
    engine = MagicMock(spec=AsyncEngine)
    connection = AsyncMock()
    connection.__aenter__.side_effect = OperationalError("private SQL", {}, Exception("secret"))
    engine.connect.return_value = connection
    assert await DatabaseReadinessProbe(cast(AsyncEngine, engine), 1).is_ready() is False


async def test_database_check_obeys_deadline() -> None:
    import asyncio

    engine = MagicMock(spec=AsyncEngine)
    connection = AsyncMock()

    async def delayed_connect() -> None:
        await asyncio.sleep(1)

    connection.__aenter__.side_effect = delayed_connect
    engine.connect.return_value = connection
    assert await DatabaseReadinessProbe(cast(AsyncEngine, engine), 0.01).is_ready() is False
