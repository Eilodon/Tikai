"""
Tests for leak_detector.py
Run: pytest tests/rule_engine/test_leak_detector.py -v
"""

from decimal import Decimal

from app.services.rule_engine.leak_detector import detect_top_leaks
from app.services.rule_engine.pl_calculator import CreatorSummary, SKUSummary


def make_sku(
    sku_id="SKU-001",
    name="Test SKU",
    gmv=Decimal("100000"),
    net_revenue=Decimal("89000"),
    margin=None,
    refund_rate=Decimal("0.02"),
    gmv_rank=1,
    voucher_cost=Decimal("3000"),
    affiliate_commission=Decimal("5000"),
) -> SKUSummary:
    return SKUSummary(
        sku_id=sku_id,
        sku_name=name,
        gmv=gmv,
        net_revenue=net_revenue,
        order_count=10,
        refund_count=0,
        refund_rate=refund_rate,
        total_cogs=Decimal("50000") if margin is not None else None,
        margin=margin,
        margin_pct=None,
        affiliate_commission=affiliate_commission,
        voucher_cost=voucher_cost,
        gmv_rank=gmv_rank,
    )


def make_creator(
    creator_id="CR-001",
    name="Creator A",
    gmv=Decimal("100000"),
    commission=Decimal("5000"),
    roi=None,
) -> CreatorSummary:
    # Note: roi param name kept for test compat; mapped to revenue_efficiency
    computed_roi = roi if roi is not None else (gmv / commission if commission > 0 else None)
    return CreatorSummary(
        creator_id=creator_id,
        creator_name=name,
        attributed_gmv=gmv,
        attributed_net_revenue=gmv * Decimal("0.89"),
        total_commission=commission,
        order_count=5,
        revenue_efficiency=computed_roi,
    )


class TestDetectTopLeaks:
    def test_negative_margin_sku_appears_as_leak(self):
        skus = [make_sku(margin=Decimal("-10000"), gmv_rank=1)]
        leaks = detect_top_leaks(skus, [], {})
        assert len(leaks) == 1
        assert leaks[0].reason in ("voucher_high", "affiliate_high")
        assert leaks[0].estimated_loss == Decimal("10000")

    def test_leaks_sorted_by_estimated_loss_desc(self):
        skus = [
            make_sku("SKU-A", margin=Decimal("-5000"), gmv_rank=1),
            make_sku("SKU-B", margin=Decimal("-20000"), gmv_rank=2),
            make_sku("SKU-C", margin=Decimal("-1000"), gmv_rank=3),
        ]
        leaks = detect_top_leaks(skus, [], {})
        losses = [leak.estimated_loss for leak in leaks]
        assert losses == sorted(losses, reverse=True)

    def test_max_3_leaks_returned(self):
        skus = [make_sku(f"SKU-{i}", margin=Decimal("-1000"), gmv_rank=i) for i in range(1, 8)]
        leaks = detect_top_leaks(skus, [], {}, top_n=3)
        assert len(leaks) <= 3

    def test_cogs_missing_leak_has_zero_estimated_loss(self):
        skus = [make_sku("SKU-001", margin=None, gmv_rank=1)]
        leaks = detect_top_leaks(skus, [], {})
        cogs_leaks = [leak for leak in leaks if leak.reason == "cogs_missing"]
        assert len(cogs_leaks) == 1
        assert cogs_leaks[0].estimated_loss == Decimal("0")
        assert cogs_leaks[0].confidence == "low"

    def test_creator_roi_below_one_detected(self):
        creators = [make_creator(gmv=Decimal("50000"), commission=Decimal("60000"))]
        leaks = detect_top_leaks([], creators, {})
        creator_leaks = [leak for leak in leaks if leak.type == "creator"]
        assert len(creator_leaks) == 1
        assert creator_leaks[0].reason == "commission_exceeds_margin"

    def test_skus_beyond_rank_20_ignored(self):
        """Only top-20 SKUs by GMV should be analyzed."""
        skus = [make_sku("SKU-LOW", margin=Decimal("-99999"), gmv_rank=21)]
        leaks = detect_top_leaks(skus, [], {})
        assert len(leaks) == 0

    def test_no_leaks_returns_empty_list(self):
        skus = [make_sku("SKU-001", margin=Decimal("50000"), gmv_rank=1)]
        leaks = detect_top_leaks(skus, [], {})
        assert all(leak.reason != "refund_spike" for leak in leaks)


class TestShopCategoryBaseline:
    """v2.1.0: shop_category wires industry_data.py baselines into leak detector."""

    def test_fashion_shop_not_flagged_at_14pct(self):
        """Fashion baseline = 15% → 14% refund is below threshold (15% × 1.5 = 22.5%)."""
        sku = make_sku("SKU-FASHION", refund_rate=Decimal("0.14"), gmv_rank=1)
        leaks = detect_top_leaks([sku], [], {}, shop_category="fashion")
        refund_leaks = [leak for leak in leaks if leak.reason == "refund_spike"]
        assert len(refund_leaks) == 0, (
            "Fashion SKU at 14% should NOT be flagged — fashion baseline is 15%, "
            "threshold is 22.5%. Old 9% default would flag this at 13.5% threshold."
        )

    def test_fashion_shop_flagged_at_25pct(self):
        """Fashion baseline = 15% → 25% refund exceeds threshold (15% × 1.5 = 22.5%)."""
        sku = make_sku("SKU-FASHION", refund_rate=Decimal("0.25"), gmv_rank=1)
        leaks = detect_top_leaks([sku], [], {}, shop_category="fashion")
        refund_leaks = [leak for leak in leaks if leak.reason == "refund_spike"]
        assert len(refund_leaks) == 1

    def test_food_shop_flagged_at_8pct(self):
        """Food baseline = 5% → 8% refund exceeds threshold (5% × 1.5 = 7.5%)."""
        sku = make_sku("SKU-FOOD", refund_rate=Decimal("0.08"), gmv_rank=1)
        leaks = detect_top_leaks([sku], [], {}, shop_category="food")
        refund_leaks = [leak for leak in leaks if leak.reason == "refund_spike"]
        assert len(refund_leaks) == 1

    def test_no_category_falls_back_to_default(self):
        """Without shop_category, DEFAULT_BASELINE (9%) is used as fallback."""
        from app.services.rule_engine.baselines import DEFAULT_BASELINE

        assert DEFAULT_BASELINE == Decimal("0.09"), (
            "DEFAULT_BASELINE must be 9% — matches 'other' in industry_data.py"
        )

    def test_per_sku_override_takes_precedence_over_shop_category(self):
        """category_baselines dict wins over shop_category fallback."""
        sku = make_sku("SKU-001", refund_rate=Decimal("0.14"), gmv_rank=1)
        # Override SKU-001 to 20% → threshold = 30% → 14% is fine
        leaks = detect_top_leaks([sku], [], {"SKU-001": Decimal("0.20")}, shop_category="food")
        refund_leaks = [leak for leak in leaks if leak.reason == "refund_spike"]
        assert len(refund_leaks) == 0
