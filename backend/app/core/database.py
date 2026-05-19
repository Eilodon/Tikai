from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# ADR-ARCH-004: conservative pool sizing to avoid exhausting Supabase connection limits.
# Defaults: pool_size=5, max_overflow=10 → max 15 connections per process.
# Override via DB_POOL_SIZE / DB_MAX_OVERFLOW env vars when scaling replicas.
# Example: 2 API replicas + 1 worker → 2×15 + 10 = 40 (safe for Supabase Pro=100).
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
