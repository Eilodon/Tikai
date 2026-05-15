"""
Tests for settlement_reconciler.reconcile_settlement.
INVARIANT: tests use real Decimal inputs, no mocks.
"""

from decimal import Decimal

from app.services.parser.settlement_parser import SettlementRow
from app.services.rule_engine.settlement_reconciler import reconcile_settlement


def _make_row(
    payout: str = "0",
    fee: str = "0",
    adj_type: str = "",
    desc: str = "",
    sku: str = "",
) -> SettlementRow:
    return SettlementRow(
        payout_id="PAY001",
        order_id="ORD001",
        payout_amount=Decimal(payout),
        payout_date=None,
        status="Completed",
        fee_amount=Decimal(fee),
        adjustment_type=adj_type,
        description=desc,
        seller_sku=sku,
    )


class TestReconcileSettlement:
    def test_perfect_match_returns_matched(self):
        rows = [_make_row(payout="100000")]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.verdict == "matched"
        assert result.gap == Decimal("0")
        assert result.total_payout == Decimal("100000")

    def test_minor_gap_under_5pct(self):
        rows = [_make_row(payout="97000")]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.verdict == "minor_gap"

    def test_major_gap_between_5_and_15pct(self):
        rows = [_make_row(payout="90000")]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.verdict == "major_gap"

    def test_investigate_over_15pct(self):
        rows = [_make_row(payout="50000")]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.verdict == "investigate"

    def test_shipping_adjustment_detection_flags_high_sku(self):
        rows = [
            _make_row(payout="100000"),
            _make_row(
                fee="-150000",
                adj_type="Shipping Weight Adjustment",
                desc="Weight discrepancy",
                sku="SKU-A",
            ),
        ]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert "SKU-A" in result.high_shipping_adj_skus
        assert result.shipping_adjustments_total == Decimal("150000")
        assert any("SKU-A" in item for item in result.action_items_vi)

    def test_shipping_adjustment_below_threshold_not_flagged(self):
        rows = [
            _make_row(payout="100000"),
            _make_row(
                fee="-50000",
                adj_type="Shipping Weight Adjustment",
                desc="Weight discrepancy",
                sku="SKU-B",
            ),
        ]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert "SKU-B" not in result.high_shipping_adj_skus
        assert result.shipping_adjustments_total == Decimal("50000")

    def test_non_clawback_commissions_passed_through(self):
        rows = [_make_row(payout="100000")]
        result = reconcile_settlement(
            rows,
            expected_payout=Decimal("100000"),
            commission_on_refunded_orders=Decimal("75000"),
        )
        assert result.non_clawback_commissions == Decimal("75000")
        assert result.commission_waste_on_returns == Decimal("75000")
        assert any("Hoa hồng affiliate" in item for item in result.action_items_vi)

    def test_refund_admin_fee_detected_in_description(self):
        rows = [
            _make_row(payout="100000"),
            _make_row(fee="-5000", desc="Refund Admin Fee"),
        ]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.refund_admin_fees_total == Decimal("5000")

    def test_reserve_held_detected(self):
        rows = [
            _make_row(payout="100000"),
            _make_row(fee="-20000", adj_type="Reserve Hold", desc="performance review"),
        ]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.reserve_held == Decimal("20000")

    def test_zero_expected_payout_returns_matched_without_div_zero(self):
        rows = [_make_row(payout="0")]
        result = reconcile_settlement(rows, expected_payout=Decimal("0"))
        assert result.verdict == "matched"

    def test_negative_payout_rows_excluded_from_total(self):
        rows = [
            _make_row(payout="100000"),
            _make_row(payout="-30000"),
        ]
        result = reconcile_settlement(rows, expected_payout=Decimal("100000"))
        assert result.total_payout == Decimal("100000")
