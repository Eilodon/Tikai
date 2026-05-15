"""Tests for action_rules.py"""

from decimal import Decimal

from app.services.rule_engine.action_rules import evaluate_rules
from app.services.rule_engine.pl_calculator import CreatorSummary, SKUSummary


def make_sku(
    sku_id="SKU-001", margin=None, refund_rate=Decimal("0.02"), gmv_rank=1, cogs=Decimal("50000")
) -> SKUSummary:
    return SKUSummary(
        sku_id=sku_id,
        sku_name=f"SKU {sku_id}",
        gmv=Decimal("100000"),
        net_revenue=Decimal("89000"),
        order_count=10,
        refund_count=0,
        refund_rate=refund_rate,
        total_cogs=cogs,
        margin=margin,
        margin_pct=None,
        affiliate_commission=Decimal("5000"),
        voucher_cost=Decimal("3000"),
        gmv_rank=gmv_rank,
    )


def make_creator(roi=Decimal("0.8"), commission=Decimal("10000")) -> CreatorSummary:
    return CreatorSummary(
        creator_id="CR-001",
        creator_name="Creator A",
        attributed_gmv=Decimal("100000"),
        attributed_net_revenue=Decimal("89000"),
        total_commission=commission,
        order_count=5,
        revenue_efficiency=roi,
    )


class TestEvaluateRules:
    def test_negative_margin_triggers_reduce_voucher(self):
        skus = [make_sku(margin=Decimal("-5000"), gmv_rank=1)]
        triggers = evaluate_rules(skus, [], {})
        assert any(t.rule_id == "sku_margin_negative" for t in triggers)

    def test_creator_roi_below_one_triggers_pause(self):
        creators = [make_creator(roi=Decimal("0.7"))]
        triggers = evaluate_rules([], creators, {})
        assert any(t.rule_id == "creator_roi_below_one" for t in triggers)

    def test_cogs_missing_triggers_check_cogs(self):
        skus = [make_sku(margin=None, cogs=None, gmv_rank=1)]
        triggers = evaluate_rules(skus, [], {})
        assert any(t.rule_id == "cogs_missing_top_sku" for t in triggers)

    def test_same_entity_not_triggered_twice(self):
        # Both negative margin AND refund spike for same SKU
        skus = [
            make_sku("SKU-001", margin=Decimal("-5000"), refund_rate=Decimal("0.4"), gmv_rank=1)
        ]
        baselines = {"SKU-001": Decimal("0.05")}
        triggers = evaluate_rules(skus, [], baselines)
        sku_triggers = [t for t in triggers if t.entity_id == "SKU-001"]
        rule_ids = [t.rule_id for t in sku_triggers]
        # Each rule should appear max once per entity
        assert len(rule_ids) == len(set(rule_ids))

    def test_sorted_by_priority_ascending(self):
        skus = [make_sku(margin=Decimal("-5000"), gmv_rank=1)]
        creators = [make_creator(roi=Decimal("0.7"))]
        triggers = evaluate_rules(skus, creators, {})
        priorities = [t.priority for t in triggers]
        assert priorities == sorted(priorities)

    def test_skus_beyond_rank_20_not_triggered(self):
        skus = [make_sku("SKU-DEEP", margin=Decimal("-99999"), gmv_rank=21)]
        triggers = evaluate_rules(skus, [], {})
        assert not any(t.entity_id == "SKU-DEEP" for t in triggers)

    def test_creator_with_zero_commission_not_triggered(self):
        creators = [make_creator(roi=None, commission=Decimal("0"))]
        triggers = evaluate_rules([], creators, {})
        assert not any(t.rule_id == "creator_roi_below_one" for t in triggers)
