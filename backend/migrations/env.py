import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from noris_ai.chat import models as chat_models
from noris_ai.core.config import Settings
from noris_ai.db.base import Base

# Importing the chat models registers the Etappe 3 tables on the shared
# declarative metadata; bind it explicitly for Alembic autogeneration.
TARGET_METADATA = chat_models.Base.metadata
if TARGET_METADATA is not Base.metadata:  # pragma: no cover - metadata identity
    raise RuntimeError("Chat models must register on the shared declarative base")

config = context.config
settings = Settings()
migration_url = (settings.migration_database_url or settings.database_url).get_secret_value()
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def configure_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(migration_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(configure_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=migration_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
