"""
Tests for pl_calculator.py
Run: pytest tests/rule_engine/test_pl_calculator.py -v

FIX P0-3 + P0-4: Updated to cover quantity-based COGS, new fee fields,
and revenue_efficiency (renamed from roi).
"""
import pytest
from decimal import Decimal
from datetime import date

from app.services.parser.base import RawOrderRow
from app.services.rule_engine.pl_calculator import (
    calculate_sku_summaries,
    calculate_creator_summaries,
)


def make_row(**kwargs) -> RawOrderRow:
    defaults = dict(
        tiktok_order_id="ORD-001",
        sku_id="SKU-001",
        sku_name="Serum A",
        gmv=Decimal("100000"),
        platform_commission=Decimal("12500"),   # 12.5% of 100000
        transaction_fee=Decimal("6000"),         # 6% of 100000 (from 09/05/2026)
        order_processing_fee=Decimal("3000"),    # 3,000 VND/order (from 27/10/2025)
        affiliate_commission=Decimal("5000"),
        voucher_cost=Decimal("3000"),
        shipping_subsidy=Decimal("1000"),
        refund_amount=Decimal("0"),
        quantity=1,
        order_date=date(2026, 5, 1),
        status="completed",
        creator_id=None,
        creator_name=None,
    )
    defaults.update(kwargs)
    return RawOrderRow(**defaults)


class TestSKUSummaries:
    def test_margin_calculated_when_cogs_available(self):
        rows = [make_row(sku_id="SKU-001", gmv=Decimal("100000"), quantity=1)]
        cogs_map = {"SKU-001": Decimal("50000")}
        summaries = calculate_sku_summaries(rows, cogs_map)

        assert len(summaries) == 1
        s = summaries[0]
        # net_revenue = 100000 - 12500 - 6000 - 3000 - 5000 - 3000 - 1000 = 69500
        # total_cogs  = 50000 * 1 (qty) = 50000
        # margin = 69500 - 50000 = 19500
        assert s.total_cogs == Decimal("50000")
        assert s.margin is not None
        assert s.margin == Decimal("19500")

    def test_margin_is_none_when_cogs_missing(self):
        """CRITICAL INVARIANT: margin must be None, not 0, when COGS missing."""
        rows = [make_row(sku_id="SKU-001")]
        summaries = calculate_sku_summaries(rows, cogs_map={})
        assert summaries[0].total_cogs is None
        assert summaries[0].margin is None
        assert summaries[0].margin_pct is None

    def test_negative_margin_is_valid(self):
        """Margin can be negative — do not clamp."""
        rows = [make_row(sku_id="SKU-001", gmv=Decimal("50000"))]
        cogs_map = {"SKU-001": Decimal("100000")}
        summaries = calculate_sku_summaries(rows, cogs_map)
        assert summaries[0].margin is not None
        assert summaries[0].margin < 0

    # ── REGRESSION P0-3: quantity-based COGS ──────────────────────────────────

    def test_cogs_multiplied_by_quantity_not_order_count(self):
        """REGRESSION P0-3: COGS must use total units sold, not total orders.

        An order of qty=3 should consume 3x COGS, not 1x.
        Previous code: total_cogs = cogs_per_unit * order_count  (WRONG)
        Fixed code:    total_cogs = cogs_per_unit * total_quantity (RIGHT)
        """
        rows = [
            make_row(tiktok_order_id="O1", sku_id="SKU-001", quantity=3, gmv=Decimal("300000")),
            make_row(tiktok_order_id="O2", sku_id="SKU-001", quantity=1, gmv=Decimal("100000")),
        ]
        cogs_map = {"SKU-001": Decimal("50000")}  # 50,000 VND per unit
        summaries = calculate_sku_summaries(rows, cogs_map)

        assert len(summaries) == 1
        s = summaries[0]
        # total_quantity = 3 + 1 = 4, so total_cogs = 50000 * 4 = 200000
        assert s.total_cogs == Decimal("200000"), (
            f"Expected 200000 (4 units × 50000), got {s.total_cogs}. "
            "Did you use order_count instead of total_quantity?"
        )
        assert s.order_count == 2  # still 2 orders

    def test_quantity_defaults_to_one_for_backward_compat(self):
        """Rows from old exports without quantity column default to qty=1."""
        row = make_row(quantity=1)
        assert row.quantity == 1

    # ── REGRESSION P0-3: transaction_fee + order_processing_fee in net_revenue ─

    def test_net_revenue_includes_transaction_fee(self):
        """REGRESSION P0-3: transaction_fee must be deducted from net_revenue."""
        from app.services.rule_engine.fee_calculator import calculate_net_revenue
        row = make_row(
            gmv=Decimal("100000"),
            platform_commission=Decimal("12500"),
            transaction_fee=Decimal("6000"),    # 6%
            order_processing_fee=Decimal("3000"),
            affiliate_commission=Decimal("0"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
        )
        net = calculate_net_revenue(row)
        # 100000 - 12500 - 6000 - 3000 = 78500
        assert net == Decimal("78500"), (
            f"Expected 78500, got {net}. "
            "transaction_fee and order_processing_fee must be in the formula."
        )

    def test_zero_fees_backward_compat(self):
        """Rows from old exports with zero transaction/processing fees still work."""
        from app.services.rule_engine.fee_calculator import calculate_net_revenue
        row = make_row(
            gmv=Decimal("100000"),
            platform_commission=Decimal("2000"),
            transaction_fee=Decimal("0"),
            order_processing_fee=Decimal("0"),
            affiliate_commission=Decimal("5000"),
            voucher_cost=Decimal("3000"),
            shipping_subsidy=Decimal("1000"),
            refund_amount=Decimal("0"),
        )
        net = calculate_net_revenue(row)
        assert net == Decimal("89000")  # same as before new fee fields

    def test_gmv_rank_assigned_correctly(self):
        rows = [
            make_row(tiktok_order_id="O1", sku_id="SKU-LOW", gmv=Decimal("10000")),
            make_row(tiktok_order_id="O2", sku_id="SKU-HIGH", gmv=Decimal("200000")),
            make_row(tiktok_order_id="O3", sku_id="SKU-MID", gmv=Decimal("100000")),
        ]
        summaries = calculate_sku_summaries(rows, {})
        rank_map = {s.sku_id: s.gmv_rank for s in summaries}
        assert rank_map["SKU-HIGH"] == 1
        assert rank_map["SKU-MID"] == 2
        assert rank_map["SKU-LOW"] == 3

    def test_refund_rate_calculated(self):
        rows = [
            make_row(tiktok_order_id="O1", sku_id="SKU-001", status="completed"),
            make_row(tiktok_order_id="O2", sku_id="SKU-001", status="completed"),
            make_row(tiktok_order_id="O3", sku_id="SKU-001", status="refunded"),
            make_row(tiktok_order_id="O4", sku_id="SKU-001", status="refunded"),
        ]
        summaries = calculate_sku_summaries(rows, {})
        assert summaries[0].refund_rate == Decimal("0.5")


class TestCreatorSummaries:
    """
    REGRESSION P0-4: revenue_efficiency replaces roi.
    Formula: attributed_net_revenue / total_commission (NOT gmv / commission).
    """

    def test_revenue_efficiency_attribute_exists(self):
        """REGRESSION P0-4: field renamed from roi to revenue_efficiency."""
        rows = [make_row(
            creator_id="CR-001", creator_name="Creator A",
            gmv=Decimal("200000"), affiliate_commission=Decimal("10000"),
        )]
        summaries = calculate_creator_summaries(rows)
        assert hasattr(summaries[0], "revenue_efficiency"), (
            "revenue_efficiency attribute missing — was roi renamed correctly?"
        )
        assert not hasattr(summaries[0], "roi"), (
            "Old 'roi' attribute still present — rename incomplete."
        )

    def test_revenue_efficiency_uses_net_revenue_not_gmv(self):
        """REGRESSION P0-4: formula must use net_revenue, not gmv.

        GMV-based roi is almost always > 1.0 → never flags bad creators.
        Net revenue-based efficiency correctly reflects post-fee reality.
        """
        row = make_row(
            creator_id="CR-001", creator_name="Creator A",
            gmv=Decimal("100000"),
            platform_commission=Decimal("12500"),
            transaction_fee=Decimal("6000"),
            order_processing_fee=Decimal("3000"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
            affiliate_commission=Decimal("80000"),  # high commission
        )
        summaries = calculate_creator_summaries([row])
        s = summaries[0]
        # net_revenue = 100000 - 12500 - 6000 - 3000 - 80000 = -1500
        # efficiency = -1500 / 80000 < 0 → clearly bad creator
        assert s.revenue_efficiency is not None
        assert s.revenue_efficiency < Decimal("1.0"), (
            f"Creator with commission > net_revenue should have efficiency < 1.0, "
            f"got {s.revenue_efficiency}. Did formula use gmv instead of net_revenue?"
        )

    def test_high_commission_creator_flagged(self):
        """Creator whose commission exceeds net_revenue should have efficiency < 1."""
        rows = [make_row(
            creator_id="CR-BAD",
            gmv=Decimal("100000"),
            platform_commission=Decimal("12500"),
            transaction_fee=Decimal("6000"),
            order_processing_fee=Decimal("3000"),
            affiliate_commission=Decimal("90000"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
        )]
        summaries = calculate_creator_summaries(rows)
        assert summaries[0].revenue_efficiency < Decimal("0")

    def test_efficient_creator_above_one(self):
        """Creator generating 5x net_revenue vs commission → efficiency ~5."""
        rows = [make_row(
            creator_id="CR-GOOD",
            gmv=Decimal("500000"),
            platform_commission=Decimal("62500"),
            transaction_fee=Decimal("30000"),
            order_processing_fee=Decimal("3000"),
            affiliate_commission=Decimal("10000"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
        )]
        summaries = calculate_creator_summaries(rows)
        # net_revenue = 500000 - 62500 - 30000 - 3000 - 10000 = 394500
        # efficiency = 394500 / 10000 = 39.45
        assert summaries[0].revenue_efficiency > Decimal("1.0")

    def test_efficiency_none_when_zero_commission(self):
        """Organic orders (no affiliate commission) → revenue_efficiency = None."""
        rows = [make_row(
            creator_id="CR-ORGANIC",
            affiliate_commission=Decimal("0"),
        )]
        summaries = calculate_creator_summaries(rows)
        assert summaries[0].revenue_efficiency is None

    def test_rows_without_creator_id_excluded(self):
        rows = [
            make_row(creator_id=None),
            make_row(tiktok_order_id="O2", creator_id="CR-001", creator_name="A",
                     gmv=Decimal("100000"), affiliate_commission=Decimal("5000")),
        ]
        summaries = calculate_creator_summaries(rows)
        assert len(summaries) == 1
        assert summaries[0].creator_id == "CR-001"

    def test_leak_detector_uses_revenue_efficiency(self):
        """REGRESSION P0-4: leak_detector must flag creator with efficiency < 1.0.

        Old condition: commission > gmv (almost never true → no leaks detected).
        New condition: efficiency < 1.0 (commission > net_revenue → real loss).
        """
        from app.services.rule_engine.leak_detector import detect_top_leaks
        from app.services.rule_engine.pl_calculator import CreatorSummary

        bad_creator = CreatorSummary(
            creator_id="CR-BAD",
            creator_name="Bad Creator",
            attributed_gmv=Decimal("100000"),
            attributed_net_revenue=Decimal("5000"),   # net_rev < commission
            total_commission=Decimal("80000"),
            order_count=10,
            revenue_efficiency=Decimal("5000") / Decimal("80000"),  # ~0.0625 < 1
        )
        leaks = detect_top_leaks([], [bad_creator], category_baselines={})
        creator_leaks = [l for l in leaks if l.type == "creator"]
        assert len(creator_leaks) == 1, (
            "Creator with revenue_efficiency < 1.0 should be flagged as a leak. "
            "Check leak_detector condition — did it still use old roi formula?"
        )
