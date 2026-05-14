"""Tests for v0.5.2 bug fixes from code review audit."""
from decimal import Decimal


class TestWorkerEstimatedSavedFix:
    """Verify FIX v0.5.2: worker.py line 133 was hardcoding Decimal('0').

    This is a static-source-check style test since the worker function is async +
    requires DB. The cheapest, most reliable signal is: the code path that builds
    WeeklyReceipt() must reference total_estimated, not Decimal('0').
    """

    def test_worker_passes_total_estimated_to_db_save(self):
        import inspect
        from app.tasks import worker
        source = inspect.getsource(worker.run_weekly_receipts)
        # Locate the WeeklyReceipt(...) constructor call and confirm
        # total_estimated_saved=total_estimated appears AFTER the AI input dict
        assert "total_estimated_saved=total_estimated," in source, (
            "WeeklyReceipt save must use total_estimated, not hardcoded Decimal('0'). "
            "Re-check worker.py — was this fix accidentally reverted?"
        )
        # Also assert no surviving Decimal('0') in the receipt save block
        # (the AI input above might use it, but the DB save MUST NOT)
        receipt_block_start = source.find("receipt = WeeklyReceipt(")
        receipt_block_end = source.find(")", receipt_block_start)
        receipt_block = source[receipt_block_start:receipt_block_end]
        assert 'total_estimated_saved=Decimal("0")' not in receipt_block, (
            "WeeklyReceipt DB save still has hardcoded Decimal('0') for estimated_saved"
        )


class TestEntityIdResolution:
    """FIX v0.5.2: _resolve_entity_id should prefer source_insight_json.entity
    (set per-action at creation time) over first-match-by-rule-id from triggers.
    """

    def test_uses_source_insight_json_entity_directly(self):
        from app.tasks.verify_action_impact import _resolve_entity_id

        class FakeAction:
            rule_trigger = "sku_margin_negative"
            source_insight_json = {"entity": "SKU-CORRECT-123", "trigger": "sku_margin_negative"}

        class FakeSnapshot:
            # action_triggers_json has DIFFERENT entity (would be wrong if we matched first)
            action_triggers_json = [
                {"rule_id": "sku_margin_negative", "entity_id": "SKU-WRONG-FIRST"},
                {"rule_id": "sku_margin_negative", "entity_id": "SKU-CORRECT-123"},
            ]

        result = _resolve_entity_id(FakeAction(), FakeSnapshot())
        assert result == "SKU-CORRECT-123", (
            f"Expected entity from source_insight_json.entity, got {result!r}. "
            "v0.5.2 fix is missing — verify_action_impact would attribute deltas to wrong SKU."
        )

    def test_falls_back_to_triggers_for_legacy_actions(self):
        """Legacy actions (pre-v0.4) have no entity in source_insight_json."""
        from app.tasks.verify_action_impact import _resolve_entity_id

        class LegacyAction:
            rule_trigger = "sku_margin_negative"
            source_insight_json = {"trigger": "sku_margin_negative"}  # no "entity" key

        class FakeSnapshot:
            action_triggers_json = [
                {"rule_id": "sku_refund_spike", "entity_id": "SKU-OTHER"},
                {"rule_id": "sku_margin_negative", "entity_id": "SKU-LEGACY-MATCH"},
            ]

        result = _resolve_entity_id(LegacyAction(), FakeSnapshot())
        assert result == "SKU-LEGACY-MATCH", "Fallback to first-match-by-rule_id failed for legacy"

    def test_returns_none_when_no_match(self):
        from app.tasks.verify_action_impact import _resolve_entity_id

        class Action:
            rule_trigger = "unknown_rule"
            source_insight_json = None

        class Snapshot:
            action_triggers_json = []

        result = _resolve_entity_id(Action(), Snapshot())
        assert result is None


class TestSharedArqPool:
    """FIX v0.5.2: ARQ pool extracted to core/arq_pool.py — actions.py + imports.py share it."""

    def test_arq_pool_module_exists(self):
        from app.core import arq_pool
        assert hasattr(arq_pool, "get_arq_pool")
        assert hasattr(arq_pool, "close_arq_pool")

    def test_imports_uses_shared_pool(self):
        import inspect
        from app.api.v1 import imports
        source = inspect.getsource(imports)
        assert "from app.core.arq_pool import get_arq_pool" in source
        assert "get_arq_pool()" in source

    def test_actions_uses_shared_pool(self):
        """Critical: actions.py was creating new connection per request before v0.5.2."""
        import inspect
        from app.api.v1 import actions
        source = inspect.getsource(actions)
        assert "from app.core.arq_pool import get_arq_pool" in source
        # No more inline ArqRedis.from_url
        assert "ArqRedis.from_url" not in source, (
            "actions.py still has inline Redis connection creation. "
            "v0.5.2 fix must extract to shared pool."
        )

    def test_arq_pool_uses_lock(self):
        """Race condition prevention check."""
        import inspect
        from app.core import arq_pool
        source = inspect.getsource(arq_pool.get_arq_pool)
        assert "_arq_lock" in source, "Missing asyncio.Lock for race protection"
        assert "ping" in source, "Missing health check before pool reuse"


class TestRecomputeRateLimit:
    """FIX v0.5.2: recompute is heavy (50k orders + Rule Engine), needs rate limit."""

    def test_recompute_endpoint_has_rate_limit_decorator(self):
        import inspect
        from app.api.v1 import insights
        source = inspect.getsource(insights)
        # Rate limit decorator must appear before recompute_insight definition
        recompute_idx = source.find("async def recompute_insight")
        assert recompute_idx > 0, "recompute_insight not found"
        # Look 200 chars before for the decorator
        preceding = source[max(0, recompute_idx - 200):recompute_idx]
        assert "@limiter.limit(" in preceding, (
            "recompute_insight is missing @limiter.limit() — heavy endpoint must be rate-limited"
        )
