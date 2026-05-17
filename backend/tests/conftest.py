"""
Shared pytest fixtures.
"""

import os


def pytest_configure(config):
    """Set mock env vars so modules that call get_settings() at module import time
    don't crash in CI without a .env file. These values are never used for actual
    DB/API connections — integration tests that need real infra are explicitly skipped."""
    os.environ["DEBUG"] = "false"
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_ANON_KEY", "test_anon_key")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test_service_role_key")
    os.environ.setdefault("SUPABASE_JWT_SECRET", "test_jwt_secret_that_is_32_chars_long")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test_anthropic_key")


from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402

from app.services.parser.base import RawOrderRow  # noqa: E402
from app.services.rule_engine.fee_calculator import FeeConfigData  # noqa: E402


@pytest.fixture
def sample_rows() -> list[RawOrderRow]:
    """10 sample orders: 2 SKUs, 1 creator, 2 refunds."""
    rows = []
    for i in range(1, 11):
        rows.append(
            RawOrderRow(
                tiktok_order_id=f"ORD-{i:03d}",
                sku_id="SKU-001" if i <= 7 else "SKU-002",
                sku_name="Serum A" if i <= 7 else "Toner B",
                gmv=Decimal("100000") if i <= 7 else Decimal("80000"),
                platform_commission=Decimal("2000") if i <= 7 else Decimal("1600"),
                affiliate_commission=Decimal("5000") if i <= 7 else Decimal("4000"),
                voucher_cost=Decimal("3000") if i <= 7 else Decimal("2400"),
                shipping_subsidy=Decimal("1000") if i <= 7 else Decimal("800"),
                refund_amount=Decimal("100000") if i in (3, 7) else Decimal("0"),
                order_date=date(2026, 5, i if i <= 7 else i - 4),
                status="refunded" if i in (3, 7) else "completed",
                creator_id="CR-001" if i <= 5 else None,
                creator_name="Creator A" if i <= 5 else None,
            )
        )
    return rows


@pytest.fixture
def sample_fee_config() -> FeeConfigData:
    return FeeConfigData(
        version="2024-VN-v1",
        platform_commission_rate=Decimal("0.02"),
        category_overrides={},
    )
