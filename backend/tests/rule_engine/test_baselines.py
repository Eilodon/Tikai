"""Test category refund baselines (FIX BUG-H5)."""

from decimal import Decimal

from app.services.rule_engine.baselines import (
    DEFAULT_BASELINE,
    get_baseline_for_category,
)


class TestBaselines:
    def test_default_baseline_is_realistic(self):
        # Old hardcoded was 5%; new default is 8% (median across categories)
        assert DEFAULT_BASELINE == Decimal("0.08")

    def test_fashion_high_baseline(self):
        # Fashion has highest refund rate (size/fit issues)
        assert get_baseline_for_category("fashion") >= Decimal("0.15")

    def test_food_low_baseline(self):
        # Food is hard to return, low baseline
        assert get_baseline_for_category("food") <= Decimal("0.05")

    def test_unknown_category_returns_default(self):
        assert get_baseline_for_category("unknown_xyz") == DEFAULT_BASELINE
        assert get_baseline_for_category(None) == DEFAULT_BASELINE
        assert get_baseline_for_category("") == DEFAULT_BASELINE

    def test_case_insensitive_lookup(self):
        assert get_baseline_for_category("BEAUTY") == get_baseline_for_category("beauty")
        assert get_baseline_for_category("Mother-Baby") == get_baseline_for_category("mother_baby")
