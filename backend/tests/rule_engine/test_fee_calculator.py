"""
Tests for fee_calculator.py
Run: pytest tests/rule_engine/test_fee_calculator.py -v
"""

from datetime import date
from decimal import Decimal

from app.services.parser.base import RawOrderRow
from app.services.rule_engine.fee_calculator import (
    FeeConfigData,
    apply_fee_config,
    calculate_net_revenue,
    safe_divide,
)


def make_row(**kwargs) -> RawOrderRow:
    defaults = dict(
        tiktok_order_id="ORD-001",
        sku_id="SKU-001",
        sku_name="Test SKU",
        gmv=Decimal("100000"),
        platform_commission=Decimal("2000"),
        affiliate_commission=Decimal("5000"),
        voucher_cost=Decimal("3000"),
        shipping_subsidy=Decimal("1000"),
        refund_amount=Decimal("0"),
        order_date=date(2026, 5, 1),
        status="completed",
    )
    defaults.update(kwargs)
    return RawOrderRow(**defaults)


class TestCalculateNetRevenue:
    def test_standard_order(self):
        row = make_row(
            gmv=Decimal("100000"),
            platform_commission=Decimal("2000"),
            affiliate_commission=Decimal("5000"),
            voucher_cost=Decimal("3000"),
            shipping_subsidy=Decimal("1000"),
            refund_amount=Decimal("0"),
        )
        result = calculate_net_revenue(row)
        assert result == Decimal("89000")

    def test_result_is_decimal_not_float(self):
        """CRITICAL INVARIANT: result must be Decimal, never float."""
        row = make_row()
        result = calculate_net_revenue(row)
        assert isinstance(result, Decimal), f"Expected Decimal, got {type(result)}"

    def test_negative_net_revenue_is_valid(self):
        """Net revenue CAN be negative when voucher > GMV. Do not clamp to 0."""
        row = make_row(
            gmv=Decimal("50000"),
            voucher_cost=Decimal("60000"),
            platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
        )
        result = calculate_net_revenue(row)
        assert result == Decimal("-10000")
        assert result < 0

    def test_full_refund_order(self):
        row = make_row(
            gmv=Decimal("100000"),
            refund_amount=Decimal("100000"),
            platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
        )
        result = calculate_net_revenue(row)
        assert result == Decimal("0")

    def test_zero_gmv(self):
        row = make_row(
            gmv=Decimal("0"),
            platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
        )
        result = calculate_net_revenue(row)
        assert result == Decimal("0")


class TestSafeDivide:
    def test_normal_division(self):
        result = safe_divide(Decimal("100"), Decimal("4"))
        assert result == Decimal("25")

    def test_zero_denominator_returns_default(self):
        """CRITICAL: must never raise ZeroDivisionError."""
        result = safe_divide(Decimal("100"), Decimal("0"))
        assert result == Decimal("0")

    def test_zero_denominator_custom_default(self):
        result = safe_divide(Decimal("100"), Decimal("0"), default=Decimal("-1"))
        assert result == Decimal("-1")

    def test_result_is_decimal(self):
        result = safe_divide(Decimal("1"), Decimal("3"))
        assert isinstance(result, Decimal)


class TestApplyFeeConfig:
    def test_estimates_commission_when_zero(self):
        """If commission=0 but config rate > 0, estimate from config."""
        fee_config = FeeConfigData(
            version="2024-VN-v1",
            platform_commission_rate=Decimal("0.02"),
            category_overrides={},
        )
        row = make_row(gmv=Decimal("100000"), platform_commission=Decimal("0"))
        updated_rows, notes = apply_fee_config([row], fee_config)

        assert len(updated_rows) == 1
        assert updated_rows[0].platform_commission == Decimal("2000")
        assert len(notes) == 1
        assert "ORD-001" in notes[0]

    def test_does_not_change_existing_commission(self):
        fee_config = FeeConfigData(
            version="2024-VN-v1",
            platform_commission_rate=Decimal("0.02"),
            category_overrides={},
        )
        row = make_row(gmv=Decimal("100000"), platform_commission=Decimal("1500"))
        updated_rows, notes = apply_fee_config([row], fee_config)

        assert updated_rows[0].platform_commission == Decimal("1500")
        assert len(notes) == 0

    def test_does_not_raise_on_bad_row(self):
        """INVARIANT: never raise, just note discrepancy."""
        fee_config = FeeConfigData(
            version="2024-VN-v1",
            platform_commission_rate=Decimal("0.02"),
            category_overrides={},
        )
        rows = [make_row(gmv=Decimal("0"), platform_commission=Decimal("0"))]
        updated_rows, notes = apply_fee_config(rows, fee_config)
        assert len(updated_rows) == 1
