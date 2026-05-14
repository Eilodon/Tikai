import asyncio
from logging.config import fileConfig
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import all models so Alembic can detect them
from app.core.config import get_settings
from app.models.base import Base
from app.models import shop, order, import_session, fee_config, insight_snapshot, ai_action  # noqa: F401

settings = get_settings()
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "+psycopg2"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


_MIGRATION_LOCK_ID = 8765432187654321  # arbitrary stable int — unique per Tikai deployment


def do_run_migrations(connection: Connection) -> None:
    # pg_advisory_lock blocks until the lock is available, then holds it for the
    # duration of this connection. When multiple replicas start together, only one
    # runs migrations; the others wait, then find nothing to migrate and exit.
    connection.execute(text(f"SELECT pg_advisory_lock({_MIGRATION_LOCK_ID})"))
    try:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.execute(text(f"SELECT pg_advisory_unlock({_MIGRATION_LOCK_ID})"))


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
