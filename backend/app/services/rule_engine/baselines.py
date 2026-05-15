"""
Category Refund Baselines — FIX BUG-H5.

INVARIANT: these are median refund rates by category for TikTok Shop Vietnam,
based on research data (May 2026). Used as calibration for refund spike detection.

Without accurate baselines:
- Fashion/Apparel (real ~18%) → 5% baseline → false positive floods (7.5% threshold)
- Beauty (real ~8%) → 5% baseline → threshold 7.5% misses real spikes at 9-10%
- Food (real ~4%) → 5% baseline → threshold 7.5% is too high, misses real 6% spikes

Category IDs from TikTok Shop VN Seller Center category taxonomy.
"""

from decimal import Decimal

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

# Global fallback used when no category match
DEFAULT_BASELINE = Decimal("0.08")  # 8% — more realistic than old hardcoded 5%

# For detect_top_leaks: keyed by sku_id (populated at import time if category known)
# This is the dict passed as category_baselines to the Rule Engine
# In current v0.x, we use DEFAULT_BASELINE for all SKUs (no per-SKU category data yet)
# In v1.x, this will be populated from SKU category metadata
CATEGORY_REFUND_BASELINES: dict[str, Decimal] = {}
# Empty dict causes detect_top_leaks to use DEFAULT_BASELINE (overridden below)
# See leak_detector.py: `baseline = category_baselines.get(sku.sku_id, DEFAULT_BASELINE)`


def get_baseline_for_category(category_slug: str | None) -> Decimal:
    """Lookup refund baseline by category slug. Falls back to DEFAULT_BASELINE."""
    if not category_slug:
        return DEFAULT_BASELINE
    slug = category_slug.lower().replace(" ", "_").replace("-", "_")
    return CATEGORY_REFUND_BASELINES_BY_SLUG.get(slug, DEFAULT_BASELINE)
