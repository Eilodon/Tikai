"""Test BUG-NH2 fix: margin_pct uses GMV as denominator."""

from datetime import date
from decimal import Decimal

from app.services.parser.base import RawOrderRow
from app.services.rule_engine.pl_calculator import calculate_sku_summaries


def _make_row(sku_id, gmv, fees=Decimal("0"), voucher=Decimal("0"), refund=Decimal("0"), qty=1):
    return RawOrderRow(
        tiktok_order_id=f"O{sku_id}",
        sku_id=sku_id,
        sku_name=f"SKU {sku_id}",
        gmv=gmv,
        platform_commission=fees,
        affiliate_commission=Decimal("0"),
        voucher_cost=voucher,
        shipping_subsidy=Decimal("0"),
        refund_amount=refund,
        order_date=date(2026, 5, 9),
        status="completed",
        quantity=qty,
        transaction_fee=Decimal("0"),
        order_processing_fee=Decimal("0"),
    )


class TestMarginPctFix:
    def test_margin_pct_uses_gmv_denominator(self):
        # GMV=1M, fees=80k, COGS=200k → NetRev=920k, Margin=720k
        # Old (buggy): 720/920 = 78.3% (inflated)
        # New (fixed): 720/1000 = 72.0% (correct on GMV basis)
        rows = [_make_row("SKU1", Decimal("1000000"), fees=Decimal("80000"))]
        summaries = calculate_sku_summaries(rows, cogs_map={"SKU1": Decimal("200000")})
        s = summaries[0]
        assert s.margin == Decimal("720000")
        assert s.margin_pct == Decimal("0.72")  # NOT 0.78

    def test_margin_pct_negative_net_revenue_does_not_flip_sign(self):
        # Voucher exceeds GMV → negative net_revenue
        # Old (buggy): margin/net_rev with both negative → POSITIVE (sign flip!)
        # New (fixed): margin/gmv → correctly negative
        rows = [
            _make_row("LOSS", Decimal("100000"), voucher=Decimal("120000"), fees=Decimal("8000"))
        ]
        summaries = calculate_sku_summaries(rows, cogs_map={"LOSS": Decimal("30000")})
        s = summaries[0]
        # NetRev = 100k - 8k - 120k = -28k
        # Margin = -28k - 30k = -58k
        # Old buggy: -58/-28 = +2.07 (POSITIVE, misleading)
        # New: -58/100 = -0.58 (correctly negative)
        assert s.net_revenue == Decimal("-28000")
        assert s.margin == Decimal("-58000")
        assert s.margin_pct == Decimal("-0.58")
        assert s.margin_pct < 0  # critical: must be negative for loss

    def test_margin_pct_none_when_gmv_zero(self):
        rows = [_make_row("FREE", Decimal("0"))]
        summaries = calculate_sku_summaries(rows, cogs_map={"FREE": Decimal("100")})
        s = summaries[0]
        assert s.margin_pct is None  # safe_divide returns None for zero

    def test_margin_pct_none_when_cogs_missing(self):
        rows = [_make_row("NO_COGS", Decimal("1000000"))]
        summaries = calculate_sku_summaries(rows, cogs_map={})
        s = summaries[0]
        assert s.total_cogs is None
        assert s.margin is None
        assert s.margin_pct is None
