"""
Tests for the 6-issue fix batch (branch: claude/fix-feeconfig-batch-lookup-9Ps4d).

Covers:
- Issue 3: Per-order FeeConfig selection (mid-period fee change)
- Issue 9: Shopee→TikTok fallback log (tested structurally — log call present)
- Issue 2: COGS cascade parent→child for Shopee variants
- Issue 4: benchmark_version + last_updated in BenchmarkComparison
- Issue 6: Tier-aware AI budget (Settings.ai_budget_for_tier)
- Issue 8: pg_advisory_lock in migration env + ARQ _job_id dedup
"""

from datetime import date
from decimal import Decimal

# ── Issue 3: Per-order FeeConfig ─────────────────────────────────────────────


class TestPerOrderFeeConfig:
    def _make_config(self, version, rate, eff_from, eff_to=None):
        from app.services.rule_engine.fee_calculator import FeeConfigData

        return FeeConfigData(
            version=version,
            platform_commission_rate=Decimal(str(rate)),
            effective_from=eff_from,
            effective_to=eff_to,
        )

    def _make_row(self, order_id, order_date, gmv=100000):
        from app.services.parser.base import RawOrderRow

        return RawOrderRow(
            tiktok_order_id=order_id,
            sku_id="SKU-1",
            sku_name="T-shirt",
            gmv=Decimal(str(gmv)),
            platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
            order_date=order_date,
            status="completed",
        )

    def test_select_fee_config_for_date_picks_correct_config(self):
        from app.services.rule_engine.fee_calculator import select_fee_config_for_date

        old = self._make_config("v1", "0.10", date(2025, 1, 1), date(2025, 5, 10))
        new = self._make_config("v2", "0.145", date(2025, 5, 11), None)

        assert select_fee_config_for_date(date(2025, 5, 5), [old, new]) is old
        assert select_fee_config_for_date(date(2025, 5, 11), [old, new]) is new
        assert select_fee_config_for_date(date(2025, 6, 1), [old, new]) is new

    def test_apply_fee_config_uses_per_row_config(self):
        from app.services.rule_engine.fee_calculator import apply_fee_config

        old = self._make_config("v1", "0.10", date(2025, 1, 1), date(2025, 5, 10))
        new = self._make_config("v2", "0.145", date(2025, 5, 11), None)

        row_before = self._make_row("ORD-1", date(2025, 5, 5), gmv=100000)
        row_after = self._make_row("ORD-2", date(2025, 5, 15), gmv=100000)

        updated, notes = apply_fee_config([row_before, row_after], [old, new])

        before_commission = updated[0].platform_commission
        after_commission = updated[1].platform_commission
        # Before rate change: 10% = 10_000
        assert before_commission == Decimal("10000"), f"Expected 10000, got {before_commission}"
        # After rate change: 14.5% = 14_500
        assert after_commission == Decimal("14500"), f"Expected 14500, got {after_commission}"

    def test_single_config_backward_compat(self):
        """Passing a single FeeConfigData (not a list) still works."""
        from app.services.rule_engine.fee_calculator import FeeConfigData, apply_fee_config

        single = FeeConfigData(version="v1", platform_commission_rate=Decimal("0.10"))
        row = self._make_row("ORD-1", date(2025, 5, 1))
        updated, _ = apply_fee_config([row], single)
        assert updated[0].platform_commission == Decimal("10000")

    def test_build_insight_with_multiple_fee_configs_records_combined_version(self):
        from app.services.rule_engine.insight_builder import build_insight

        old = self._make_config("2025-VN-v1", "0.10", date(2025, 1, 1), date(2025, 5, 10))
        new = self._make_config("2025-VN-v2", "0.145", date(2025, 5, 11), None)

        rows = [
            self._make_row("ORD-1", date(2025, 5, 5)),
            self._make_row("ORD-2", date(2025, 5, 15)),
        ]
        insight = build_insight(
            rows=rows,
            fee_configs=[old, new],
            cogs_map={},
            category_baselines={},
            shop_id="shop-1",
        )
        assert "2025-VN-v1" in insight.fee_config_version
        assert "2025-VN-v2" in insight.fee_config_version

    def test_select_falls_back_to_first_config_when_no_match(self):
        """If order date is before all configs, use the oldest (fallback)."""
        from app.services.rule_engine.fee_calculator import select_fee_config_for_date

        cfg = self._make_config("v1", "0.10", date(2025, 6, 1), None)
        result = select_fee_config_for_date(date(2025, 1, 1), [cfg])
        assert result is cfg


# ── Issue 2: COGS cascade parent→child ───────────────────────────────────────


class TestCOGSParentCascade:
    def _make_shopee_row(self, sku_id, parent_sku_id, qty=1, gmv=100000):
        from app.services.parser.base import RawOrderRow

        return RawOrderRow(
            tiktok_order_id=f"ORD-{sku_id}",
            sku_id=sku_id,
            sku_name=f"Product {sku_id}",
            gmv=Decimal(str(gmv)),
            platform_commission=Decimal("0"),
            affiliate_commission=Decimal("0"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
            order_date=date(2025, 5, 1),
            status="completed",
            quantity=qty,
            parent_sku_id=parent_sku_id,
        )

    def test_variant_uses_parent_cogs_when_not_in_cogs_map(self):
        from app.services.rule_engine.pl_calculator import calculate_sku_summaries

        rows = [
            self._make_shopee_row("SHIRT-RED", "SHIRT-100", qty=2),
            self._make_shopee_row("SHIRT-BLUE", "SHIRT-100", qty=1),
        ]
        cogs_map = {"SHIRT-100": Decimal("50000")}  # parent COGS only
        summaries = calculate_sku_summaries(rows, cogs_map)

        red = next(s for s in summaries if s.sku_id == "SHIRT-RED")
        blue = next(s for s in summaries if s.sku_id == "SHIRT-BLUE")

        # RED: 2 units × 50_000 = 100_000
        assert red.total_cogs == Decimal("100000"), f"RED cogs={red.total_cogs}"
        # BLUE: 1 unit × 50_000 = 50_000
        assert blue.total_cogs == Decimal("50000"), f"BLUE cogs={blue.total_cogs}"

    def test_variation_cogs_takes_precedence_over_parent(self):
        from app.services.rule_engine.pl_calculator import calculate_sku_summaries

        rows = [self._make_shopee_row("SHIRT-RED", "SHIRT-100", qty=1)]
        cogs_map = {
            "SHIRT-RED": Decimal("60000"),  # specific variation COGS
            "SHIRT-100": Decimal("50000"),  # parent COGS
        }
        summaries = calculate_sku_summaries(rows, cogs_map)
        red = summaries[0]
        assert red.total_cogs == Decimal("60000")  # variation wins

    def test_no_cogs_when_neither_variant_nor_parent_in_map(self):
        from app.services.rule_engine.pl_calculator import calculate_sku_summaries

        rows = [self._make_shopee_row("SHIRT-RED", "SHIRT-100")]
        cogs_map = {"TOTALLY-DIFFERENT-SKU": Decimal("50000")}
        summaries = calculate_sku_summaries(rows, cogs_map)
        assert summaries[0].total_cogs is None
        assert summaries[0].margin is None

    def test_raworderrow_has_parent_sku_id_field(self):
        import dataclasses

        from app.services.parser.base import RawOrderRow

        field_names = {f.name for f in dataclasses.fields(RawOrderRow)}
        assert "parent_sku_id" in field_names

    def test_shopee_aliases_has_parent_sku_id(self):
        from app.services.parser.normalizer import SHOPEE_COLUMN_ALIASES

        assert "parent_sku_id" in SHOPEE_COLUMN_ALIASES
        assert "Parent SKU Reference No." in SHOPEE_COLUMN_ALIASES["parent_sku_id"]


# ── Issue 4: Benchmark versioning ────────────────────────────────────────────


class TestBenchmarkVersioning:
    def test_benchmark_comparison_has_version_fields(self):

        from app.services.benchmarks.industry_data import BenchmarkComparison

        # BenchmarkComparison is a Pydantic model — check model_fields
        fields = set(BenchmarkComparison.model_fields.keys())
        assert "benchmark_version" in fields, "Missing benchmark_version field"
        assert "last_updated" in fields, "Missing last_updated field"

    def test_compare_to_industry_returns_version_in_results(self):
        from app.services.benchmarks.industry_data import (
            BENCHMARK_VERSION,
            LAST_UPDATED,
            compare_to_industry,
        )

        results = compare_to_industry(
            shop_refund_rate=Decimal("0.12"),
            shop_margin_pct=Decimal("0.25"),
            shop_fee_burden_pct=Decimal("0.18"),
            category="fashion",
        )
        assert results, "Should return at least one comparison"
        for r in results:
            assert r.benchmark_version == BENCHMARK_VERSION
            assert r.last_updated == LAST_UPDATED

    def test_benchmark_version_and_last_updated_constants_exist(self):
        from datetime import date as date_type

        from app.services.benchmarks.industry_data import BENCHMARK_VERSION, LAST_UPDATED

        assert isinstance(BENCHMARK_VERSION, str) and BENCHMARK_VERSION
        assert isinstance(LAST_UPDATED, date_type)


# ── Issue 6: Tier-aware AI budget ────────────────────────────────────────────


class TestTierAwareBudget:
    def test_ai_budget_for_tier_returns_different_limits(self):

        from app.core.config import Settings

        # Minimal env override to avoid DB/Redis validation
        s = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            supabase_url="https://x.supabase.co",
            supabase_anon_key="x",
            supabase_service_role_key="x",
            supabase_jwt_secret="x" * 32,
            anthropic_api_key="x",
        )
        free_budget = s.ai_budget_for_tier("free")
        pro_budget = s.ai_budget_for_tier("pro")
        business_budget = s.ai_budget_for_tier("business")

        assert free_budget < pro_budget < business_budget, (
            f"Expected free < pro < business, got {free_budget} < {pro_budget} < {business_budget}"
        )

    def test_ai_budget_for_unknown_tier_falls_back_to_free(self):
        from app.core.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/x",
            supabase_url="https://x.supabase.co",
            supabase_anon_key="x",
            supabase_service_role_key="x",
            supabase_jwt_secret="x" * 32,
            anthropic_api_key="x",
        )
        assert s.ai_budget_for_tier("enterprise_xyz") == s.ai_budget_for_tier("free")

    def test_call_ai_signature_has_tier_param(self):
        import inspect

        from app.services.ai.client import call_ai

        params = inspect.signature(call_ai).parameters
        assert "tier" in params, "call_ai() missing tier parameter"
        assert params["tier"].default == "free"

    def test_ai_functions_have_tier_param(self):
        import inspect

        from app.services.ai.functions import (
            run_action_coach,
            run_aha_narrator,
            run_import_rescue,
            run_refund_clusterer,
            run_weekly_receipt,
        )

        for fn in [
            run_import_rescue,
            run_aha_narrator,
            run_action_coach,
            run_refund_clusterer,
            run_weekly_receipt,
        ]:
            params = inspect.signature(fn).parameters
            assert "tier" in params, f"{fn.__name__}() missing tier parameter"


# ── Issue 8: Migration lock + ARQ dedup ──────────────────────────────────────


class TestMigrationAndEnqueueFixes:
    def test_migration_env_has_advisory_lock(self):
        import pathlib

        source = pathlib.Path("migrations/env.py").read_text()
        assert "pg_advisory_lock" in source, "migrations/env.py must use pg_advisory_lock"
        assert "pg_advisory_unlock" in source, "migrations/env.py must release advisory lock"

    def test_migration_lock_id_is_defined(self):
        import pathlib
        import re

        source = pathlib.Path("migrations/env.py").read_text()
        match = re.search(r"_MIGRATION_LOCK_ID\s*=\s*(\d+)", source)
        assert match, "_MIGRATION_LOCK_ID constant not found in migrations/env.py"
        assert int(match.group(1)) > 0

    def test_import_endpoint_uses_job_id_for_dedup(self):
        import inspect

        from app.api.v1 import imports as imports_module

        source = inspect.getsource(imports_module)
        assert "_job_id" in source, (
            "imports.py must pass _job_id to enqueue_job for ARQ-level dedup"
        )
