"""
Seed initial TikTok VN fee config.
Run: python scripts/seed_fee_config.py
"""

import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.fee_config import FeeConfig

settings = get_settings()


async def seed():
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with async_session() as db:
        existing = await db.scalar(select(FeeConfig).where(FeeConfig.version == "2024-VN-v1"))
        if existing:
            print("✓ Fee config 2024-VN-v1 already exists")
            return

        config = FeeConfig(
            version="2024-VN-v1",
            effective_from=date(2024, 1, 1),
            effective_to=None,
            platform_commission_rate=Decimal("0.0200"),  # 2% base rate
            category_overrides={
                # Category-specific overrides — verify with TikTok docs
                # "electronics": "0.0150",
                # "beauty": "0.0200",
            },
            verified_date=date(2026, 1, 1),
            source_url="https://seller-vn.tiktok.com/university/essay?knowledge_id=10005585",
            notes=(
                "Base commission rate 2% for most categories in VN market. "
                "Verify category overrides at source URL before applying. "
                "Update version string and effective_from when rates change."
            ),
        )
        db.add(config)
        await db.commit()
        print("✓ Seeded fee config 2024-VN-v1 (platform_commission_rate=2%)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
