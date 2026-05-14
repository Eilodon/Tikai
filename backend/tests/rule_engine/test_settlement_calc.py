"""Tests for settlement_calc.py"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

from app.services.rule_engine.settlement_calc import calculate_settlement_forecast
from tests.conftest import *


def make_rows_with_dates(days_ago: list[int]) -> list:
    """Create rows placed N days ago."""
    from app.services.parser.base import RawOrderRow
    rows = []
    for i, days in enumerate(days_ago):
        rows.append(RawOrderRow(
            tiktok_order_id=f"ORD-{i:03d}",
            sku_id="SKU-001", sku_name="Test",
            gmv=Decimal("100000"),
            platform_commission=Decimal("2000"),
            affiliate_commission=Decimal("5000"),
            voucher_cost=Decimal("3000"),
            shipping_subsidy=Decimal("1000"),
            refund_amount=Decimal("0"),
            order_date=date.today() - timedelta(days=days),
            status="completed",
        ))
    return rows


class TestSettlementForecast:
    def test_recent_orders_appear_in_14d_forecast(self):
        rows = make_rows_with_dates([1, 3, 5])  # 1, 3, 5 days ago
        result = calculate_settlement_forecast(rows)
        # All should be in 14-day window (14 - days_old = days remaining)
        assert result.cash_in_14d > 0

    def test_old_orders_already_settled(self):
        rows = make_rows_with_dates([20, 30])  # Already past settlement window
        result = calculate_settlement_forecast(rows)
        assert result.settled_total > 0
        assert result.cash_in_14d == Decimal("0")

    def test_refunded_orders_excluded(self):
        from app.services.parser.base import RawOrderRow
        rows = [RawOrderRow(
            tiktok_order_id="ORD-001", sku_id="SKU-001", sku_name="Test",
            gmv=Decimal("100000"), platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"), voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"), refund_amount=Decimal("100000"),
            order_date=date.today() - timedelta(days=2),
            status="refunded",
        )]
        result = calculate_settlement_forecast(rows)
        assert result.cash_in_14d == Decimal("0")

    def test_all_decimals_not_float(self):
        rows = make_rows_with_dates([5])
        result = calculate_settlement_forecast(rows)
        assert isinstance(result.cash_in_14d, Decimal)
        assert isinstance(result.settled_total, Decimal)
        assert isinstance(result.pending_total, Decimal)
