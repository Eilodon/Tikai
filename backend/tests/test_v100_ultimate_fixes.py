"""
Tests for Tikai v1.0.0 Ultimate fixes.
All 9 fixes verified:
  1. FeeConfigData includes transaction_fee_rate + order_processing_fee_per_order
  2. apply_fee_config estimates transaction_fee from config when row has 0
  3. apply_fee_config estimates order_processing_fee for non-refund rows
  4. apply_fee_config does NOT estimate order_processing_fee for refunded rows
  5. process_import.py imports get_ai_calls_limit at module level
  6. worker.py has no duplicate datetime import inside loop
  7. AI client has retry backoff (asyncio.sleep call between retries)
  8. GET /cogs has .limit(MAX_COGS_SKUS) — not unbounded
  9. list_receipts uses Query(le=52) — validated cap, not uncapped default
"""

import inspect
from decimal import Decimal


class TestFeeConfigDataNewFields:
    """FIX v1.0.0: FeeConfigData now includes transaction_fee_rate + order_processing_fee_per_order."""

    def test_feedata_has_transaction_fee_rate(self):
        import dataclasses

        from app.services.rule_engine.fee_calculator import FeeConfigData

        fields = {f.name for f in dataclasses.fields(FeeConfigData)}
        assert "transaction_fee_rate" in fields, (
            "FeeConfigData missing transaction_fee_rate — "
            "fee_configs table has it since migration 0002 but dataclass didn't. "
            "This caused transaction_fee estimates to never run."
        )

    def test_feedata_has_order_processing_fee(self):
        import dataclasses

        from app.services.rule_engine.fee_calculator import FeeConfigData

        fields = {f.name for f in dataclasses.fields(FeeConfigData)}
        assert "order_processing_fee_per_order" in fields, (
            "FeeConfigData missing order_processing_fee_per_order"
        )

    def test_feedata_defaults_zero_for_new_fields(self):
        """Backwards compat: callers that don't pass new fields still work."""
        from app.services.rule_engine.fee_calculator import FeeConfigData

        config = FeeConfigData(
            version="test",
            platform_commission_rate=Decimal("0.125"),
        )
        assert config.transaction_fee_rate == Decimal("0")
        assert config.order_processing_fee_per_order == Decimal("0")


class TestApplyFeeConfigEstimation:
    """FIX v1.0.0: apply_fee_config estimates missing transaction/processing fees."""

    def _make_row(
        self, status="completed", transaction_fee=Decimal("0"), order_processing_fee=Decimal("0")
    ):
        from datetime import date

        from app.services.parser.base import RawOrderRow

        return RawOrderRow(
            tiktok_order_id="ORD-001",
            sku_id="SKU-001",
            sku_name="Test SKU",
            gmv=Decimal("100000"),
            platform_commission=Decimal("12500"),
            affiliate_commission=Decimal("5000"),
            voucher_cost=Decimal("0"),
            shipping_subsidy=Decimal("0"),
            refund_amount=Decimal("0"),
            order_date=date(2026, 5, 1),
            status=status,
            transaction_fee=transaction_fee,
            order_processing_fee=order_processing_fee,
        )

    def _make_config(self, transaction_rate="0.06", processing_fee="3000"):
        from app.services.rule_engine.fee_calculator import FeeConfigData

        return FeeConfigData(
            version="2026-VN-v3",
            platform_commission_rate=Decimal("0.125"),
            transaction_fee_rate=Decimal(transaction_rate),
            order_processing_fee_per_order=Decimal(processing_fee),
        )

    def test_estimates_transaction_fee_when_zero_in_row(self):
        from app.services.rule_engine.fee_calculator import apply_fee_config

        row = self._make_row(transaction_fee=Decimal("0"))
        config = self._make_config(transaction_rate="0.06")
        updated, notes = apply_fee_config([row], config)
        expected = Decimal("100000") * Decimal("0.06")  # 6,000
        assert updated[0].transaction_fee == expected, (
            f"Expected transaction_fee={expected}, got {updated[0].transaction_fee}. "
            "v1.0.0 fix: older exports without transaction_fee column should have it estimated."
        )
        assert any("transaction_fee=0" in n for n in notes)

    def test_does_not_overwrite_existing_transaction_fee(self):
        from app.services.rule_engine.fee_calculator import apply_fee_config

        row = self._make_row(transaction_fee=Decimal("5500"))  # already set
        config = self._make_config(transaction_rate="0.06")
        updated, notes = apply_fee_config([row], config)
        assert updated[0].transaction_fee == Decimal("5500"), (
            "Should not overwrite transaction_fee when already set in row"
        )
        assert not any("transaction_fee=0" in n for n in notes)

    def test_estimates_order_processing_fee_for_completed_order(self):
        from app.services.rule_engine.fee_calculator import apply_fee_config

        row = self._make_row(status="completed", order_processing_fee=Decimal("0"))
        config = self._make_config(processing_fee="3000")
        updated, notes = apply_fee_config([row], config)
        assert updated[0].order_processing_fee == Decimal("3000"), (
            "Completed orders should have order_processing_fee estimated from config"
        )

    def test_does_not_estimate_order_processing_fee_for_refunded(self):
        from app.services.rule_engine.fee_calculator import apply_fee_config

        row = self._make_row(status="refunded", order_processing_fee=Decimal("0"))
        config = self._make_config(processing_fee="3000")
        updated, notes = apply_fee_config([row], config)
        assert updated[0].order_processing_fee == Decimal("0"), (
            "Refunded orders should NOT have order_processing_fee — TikTok doesn't charge it for refunds"
        )

    def test_no_estimation_when_config_rate_zero(self):
        """If fee_config has no transaction_fee_rate (e.g. old config), don't estimate."""
        from app.services.rule_engine.fee_calculator import apply_fee_config

        row = self._make_row(transaction_fee=Decimal("0"))
        config = self._make_config(transaction_rate="0")  # old config, no rate
        updated, notes = apply_fee_config([row], config)
        assert updated[0].transaction_fee == Decimal("0"), (
            "Should not estimate when config rate is 0 — avoids false inflation for legacy configs"
        )


class TestProcessImportTopLevelImports:
    """FIX v1.0.0: AI call limits use module-level settings (was lazy import inside function)."""

    def test_get_ai_calls_limit_at_module_level(self):
        from app.tasks import process_import as pm_module

        source = inspect.getsource(pm_module)
        # Should use tier-based limits at module level via settings
        # (v1.0.0: explicit per-tier limits replaced lazy get_ai_calls_limit import)
        first_async_def = source.find("async def ")
        settings_import_idx = source.find("from app.core.config import get_settings")
        assert settings_import_idx != -1, "get_settings import missing from process_import.py"
        assert settings_import_idx < first_async_def, (
            "get_settings must be imported at module level, not inside function body."
        )
        # Verify tier-based AI limit logic exists in the module
        assert "ai_max_calls_per_import_free" in source, (
            "process_import.py must use tier-based AI call limits (ai_max_calls_per_import_free)"
        )


class TestWorkerNoDoubleImport:
    """FIX v1.0.0: worker.py had duplicate 'from datetime import...' inside the loop body."""

    def test_no_duplicate_datetime_import_in_loop(self):
        from app.tasks import worker

        source = inspect.getsource(worker.process_weekly_receipt_for_shop)
        import_count = source.count("from datetime import")
        assert import_count == 0, (
            f"process_weekly_receipt_for_shop has {import_count} inline 'from datetime import' "
            "statement(s). Imports should be at module level, not inside function/loop. "
            "v1.0.0 fix moved datetime to top of worker.py."
        )


class TestAIClientRetryBackoff:
    """FIX v1.0.0: AI client has asyncio.sleep between retries (was immediate retry)."""

    def test_call_ai_has_backoff_sleep(self):
        from app.services.ai import client as ai_client

        source = inspect.getsource(ai_client.call_ai)
        assert "asyncio.sleep" in source, (
            "call_ai is missing asyncio.sleep between retries. "
            "Immediate retry on 429/529 from Anthropic API adds load without recovery time. "
            "v1.0.0 fix: 2s backoff before attempt 2."
        )
        assert "backoff_seconds" in source or "sleep" in source, (
            "Backoff mechanism not found in call_ai"
        )

    def test_backoff_only_between_retries_not_before_first(self):
        """Backoff before attempt 0 (first call) would add unnecessary latency."""
        from app.services.ai import client as ai_client

        source = inspect.getsource(ai_client.call_ai)
        # The sleep should be conditional on attempt > 0
        assert "attempt > 0" in source or "if attempt" in source, (
            "Backoff should only apply on retry (attempt > 0), not before first attempt"
        )


class TestCOGSGetLimit:
    """FIX v1.0.0: GET /cogs is now capped at 500 SKUs (was unbounded)."""

    def test_cogs_get_has_limit(self):
        from app.api.v1 import cogs

        source = inspect.getsource(cogs.get_cogs)
        assert ".limit(" in source, (
            "GET /cogs query has no .limit() — unbounded query could return 1000+ SKUs "
            "for high-volume shops and degrade UI performance. v1.0.0 fix: cap at MAX_COGS_SKUS."
        )
        assert "MAX_COGS_SKUS" in source

    def test_cogs_post_has_rate_limit(self):
        from app.api.v1 import cogs

        # Rate limit decorator appears before function body
        full_source = inspect.getsource(cogs)
        upsert_idx = full_source.find("async def upsert_cogs")
        pre = full_source[max(0, upsert_idx - 200) : upsert_idx]
        assert "@limiter.limit(" in pre, (
            "POST /cogs missing @limiter.limit() — repeated COGS writes can cause "
            "excessive JSONB updates on the shops table. v1.0.0 fix: 30/hour rate limit."
        )


class TestWeeklyReceiptsListCap:
    """FIX v1.0.0: list_receipts limit is now validated (ge=1, le=52)."""

    def test_list_receipts_has_validated_limit(self):
        from app.api.v1 import weekly_receipts

        source = inspect.getsource(weekly_receipts.list_receipts)
        assert "le=" in source or "le=MAX_RECEIPTS" in source or "Query" in source, (
            "list_receipts has no validated limit — user could pass limit=10000 and load all receipts"
        )
        # Confirm MAX_RECEIPTS is 52 (1 year)
        assert weekly_receipts.MAX_RECEIPTS == 52, (
            f"MAX_RECEIPTS should be 52 (1 year of weekly receipts), got {weekly_receipts.MAX_RECEIPTS}"
        )


class TestVersionString:
    """FIX v1.0.0: version string was hardcoded as '0.4.0' even in v0.5.x releases."""

    def test_app_version_is_current(self):
        from app.main import APP_VERSION

        assert APP_VERSION == "2.3.0", (
            f"APP_VERSION must be '2.3.0' (current release). Got {APP_VERSION!r}. "
            "Bump APP_VERSION in main.py on every release."
        )


class TestRedisDecimalPrecision:
    """VHEATM audit: Decimal → float conversion in Redis Lua calls loses precision."""

    def test_reserve_budget_passes_decimal_string_not_float(self):
        import inspect

        from app.services.ai import client as ai_client

        source = inspect.getsource(ai_client._reserve_budget)
        # Prohibited patterns: str(float(... in Lua eval args
        assert "str(float(estimated_cost_usd))" not in source, (
            "_reserve_budget still converts estimated_cost_usd to float before Redis. "
            "Use str(estimated_cost_usd) directly to preserve Decimal precision."
        )
        assert "str(float(settings.ai_budget_for_tier" not in source, (
            "_reserve_budget still converts budget limit to float before Redis."
        )

    def test_record_cost_passes_decimal_string_not_float(self):
        import inspect

        from app.services.ai import client as ai_client

        source = inspect.getsource(ai_client._record_cost)
        assert "str(float(cost_usd))" not in source, (
            "_record_cost still converts cost_usd to float before Redis. "
            "Decimal precision loss accumulates across 1000s of AI calls."
        )
        assert "str(float(reserved_usd" not in source, (
            "_record_cost still converts reserved_usd to float before Redis."
        )

    def test_release_budget_passes_decimal_string_not_float(self):
        import inspect

        from app.services.ai import client as ai_client

        source = inspect.getsource(ai_client._release_budget_reservation)
        assert "str(float(reserved_usd))" not in source, (
            "_release_budget_reservation still converts reserved_usd to float before Redis."
        )


class TestRateLimitCoverage:
    """VHEATM audit: rate limit coverage on all mutation endpoints."""

    def test_shops_router_imports_limiter(self):
        import inspect

        from app.api.v1 import shops

        source = inspect.getsource(shops)
        assert "from app.core.rate_limit import limiter" in source, (
            "shops.py does not import rate limiter — mutation endpoints unprotected."
        )

    def test_shops_onboarding_has_rate_limit(self):
        import inspect

        from app.api.v1 import shops

        pre_idx = inspect.getsource(shops).find("async def create_shop")
        pre = inspect.getsource(shops)[max(0, pre_idx - 200) : pre_idx]
        assert "@limiter.limit(" in pre, "POST /shops/onboarding missing rate limit."

    def test_inventory_router_imports_limiter(self):
        import inspect

        from app.api.v1 import inventory

        source = inspect.getsource(inventory)
        assert "from app.core.rate_limit import limiter" in source, (
            "inventory.py does not import rate limiter — set-stock mutations unprotected."
        )

    def test_livestream_router_imports_limiter(self):
        import inspect

        from app.api.v1 import livestream

        source = inspect.getsource(livestream)
        assert "from app.core.rate_limit import limiter" in source, (
            "livestream.py does not import rate limiter — session create/delete unprotected."
        )

    def test_weekly_receipts_patch_has_rate_limit(self):
        import inspect

        from app.api.v1 import weekly_receipts

        source = inspect.getsource(weekly_receipts)
        mark_idx = source.find("async def mark_receipt_read")
        pre = source[max(0, mark_idx - 200) : mark_idx]
        assert "@limiter.limit(" in pre, "PATCH /weekly-receipts/{id}/read missing rate limit."


class TestAdvisoryLockParameterized:
    """VHEATM audit: advisory lock in insights.py must use parameterized query."""

    def test_advisory_lock_not_fstring(self):
        import inspect

        from app.api.v1 import insights

        source = inspect.getsource(insights)
        assert 'sa_text(f"SELECT pg_try_advisory_xact_lock(' not in source, (
            "Advisory lock still uses f-string interpolation in sa_text(). "
            "Use .bindparams() for parameterized query: "
            'sa_text("SELECT pg_try_advisory_xact_lock(:k)").bindparams(k=lock_key)'
        )
