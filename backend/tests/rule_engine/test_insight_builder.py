"""
Integration test — full Rule Engine pipeline.
Run: pytest tests/rule_engine/test_insight_builder.py -v
"""

from decimal import Decimal

from app.services.rule_engine.insight_builder import build_insight


class TestBuildInsight:
    def test_full_pipeline_produces_insight(self, sample_rows, sample_fee_config):
        insight = build_insight(
            rows=sample_rows,
            fee_configs=sample_fee_config,
            cogs_map={},
            category_baselines={},
            shop_id="test-shop",
        )
        assert insight.gmv_total > 0
        assert insight.total_orders == len(sample_rows)
        assert isinstance(insight.net_revenue, Decimal)

    def test_net_revenue_mode_when_no_cogs(self, sample_rows, sample_fee_config):
        insight = build_insight(
            rows=sample_rows,
            fee_configs=sample_fee_config,
            cogs_map={},
            category_baselines={},
            shop_id="test-shop",
        )
        assert insight.is_net_revenue_mode is True
        assert insight.cogs_coverage_pct == Decimal("0")

    def test_cogs_coverage_calculated(self, sample_rows, sample_fee_config):
        cogs_map = {"SKU-001": Decimal("40000")}  # only 1 of 2 SKUs
        insight = build_insight(
            rows=sample_rows,
            fee_configs=sample_fee_config,
            cogs_map=cogs_map,
            category_baselines={},
            shop_id="test-shop",
        )
        # SKU-001 has COGS, SKU-002 doesn't → coverage = 0.5
        assert insight.cogs_coverage_pct == Decimal("0.5")

    def test_empty_rows_returns_zero_insight(self, sample_fee_config):
        insight = build_insight(
            rows=[],
            fee_configs=sample_fee_config,
            cogs_map={},
            category_baselines={},
            shop_id="test-shop",
        )
        assert insight.gmv_total == Decimal("0")
        assert insight.total_orders == 0

    def test_action_triggers_generated(self, sample_rows, sample_fee_config):
        cogs_map = {"SKU-001": Decimal("200000")}  # force negative margin
        insight = build_insight(
            rows=sample_rows,
            fee_configs=sample_fee_config,
            cogs_map=cogs_map,
            category_baselines={},
            shop_id="test-shop",
        )
        trigger_rules = [t.rule_id for t in insight.action_triggers]
        assert "sku_margin_negative" in trigger_rules

    def test_period_dates_from_orders(self, sample_rows, sample_fee_config):
        from datetime import date

        insight = build_insight(
            rows=sample_rows,
            fee_configs=sample_fee_config,
            cogs_map={},
            category_baselines={},
            shop_id="test-shop",
        )
        assert insight.period_start == date(2026, 5, 1)
        assert insight.period_end == date(2026, 5, 7)
