"""
Category Refund Baselines — FIX BUG-H5.

INVARIANT: these are median refund rates by category for TikTok Shop Vietnam,
based on research data (May 2026). Used as calibration for refund spike detection.

Without accurate baselines:
- Fashion/Apparel (real ~18%) → 5% baseline → false positive floods (7.5% threshold)
- Beauty (real ~8%) → 5% baseline → threshold 7.5% misses real spikes at 9-10%
- Food (real ~4%) → 5% baseline → threshold 7.5% is too high, misses real 6% spikes

SINGLE SOURCE OF TRUTH: industry_data.py::REFUND_RATE_BENCHMARKS is the canonical
source for refund baselines. get_refund_baseline_for_shop_category() delegates to it
so the leak detector and the benchmark panel always use the same numbers.
Category IDs from TikTok Shop VN Seller Center category taxonomy.
"""

from decimal import Decimal

from app.services.benchmarks.industry_data import REFUND_RATE_BENCHMARKS

# Category slug → median refund rate (0.0 to 1.0)
# Source: TikTok Shop VN merchant data research, SEA benchmarks (Momentum Works 2025)
CATEGORY_REFUND_BASELINES_BY_SLUG: dict[str, Decimal] = {
    # Fashion & Apparel — high return due to fit/size issues
    "fashion": Decimal("0.18"),
    "clothing": Decimal("0.18"),
    "apparel": Decimal("0.18"),
    "shoes": Decimal("0.15"),
    "accessories": Decimal("0.10"),
    "bags": Decimal("0.12"),
    # Beauty & Personal Care
    "beauty": Decimal("0.08"),
    "skincare": Decimal("0.07"),
    "cosmetics": Decimal("0.08"),
    "haircare": Decimal("0.06"),
    "personal_care": Decimal("0.06"),
    # Food & Beverage — low (perishable, hard to return)
    "food": Decimal("0.03"),
    "beverage": Decimal("0.03"),
    "supplement": Decimal("0.05"),
    # Electronics — medium (defect returns)
    "electronics": Decimal("0.06"),
    "mobile": Decimal("0.05"),
    "appliances": Decimal("0.06"),
    # Home & Living
    "home": Decimal("0.09"),
    "furniture": Decimal("0.10"),
    "kitchen": Decimal("0.07"),
    # Mother & Baby
    "mother_baby": Decimal("0.07"),
    "baby_clothing": Decimal("0.09"),
    # Sports & Outdoors
    "sports": Decimal("0.08"),
    "fitness": Decimal("0.07"),
    # Pets
    "pets": Decimal("0.05"),
}

# Global fallback — matches "other" in industry_data.py so the two systems agree
DEFAULT_BASELINE: Decimal = REFUND_RATE_BENCHMARKS["other"]  # 9%

# For detect_top_leaks: keyed by sku_id (per-SKU overrides; empty = use shop fallback)
CATEGORY_REFUND_BASELINES: dict[str, Decimal] = {}


def get_baseline_for_category(category_slug: str | None) -> Decimal:
    """Lookup refund baseline by granular slug. Falls back to DEFAULT_BASELINE."""
    if not category_slug:
        return DEFAULT_BASELINE
    slug = category_slug.lower().replace(" ", "_").replace("-", "_")
    return CATEGORY_REFUND_BASELINES_BY_SLUG.get(slug, DEFAULT_BASELINE)


def get_refund_baseline_for_shop_category(category: str | None) -> Decimal:
    """Return industry-benchmark refund rate for a shop's top-level category.

    Uses industry_data.py as the single source of truth so the leak detector
    and the benchmark panel always compare against the same numbers.
    """
    if not category:
        return DEFAULT_BASELINE
    return REFUND_RATE_BENCHMARKS.get(category, DEFAULT_BASELINE)  # type: ignore[arg-type]
