from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# ADR-ARCH-004: conservative pool sizing to avoid exhausting Supabase connection limits.
# Railway free plan: 1 API replica + 1 worker replica.
# Budget per component: API=5+10=15, Worker=5+5=10 → total 25 (safe for Supabase free=15
# only with PgBouncer; safe for Pro=100). If scaling to 2 API replicas: 2×15+10=40.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
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
