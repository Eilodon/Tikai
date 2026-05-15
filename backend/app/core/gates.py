"""
Feature Gates — FIX GAP-M6: subscription tier enforcement.
Usage: require_feature(shop, Feature.RE_ANALYSIS) raises 402 if locked.
"""

from enum import StrEnum

from fastapi import HTTPException

from app.models.shop import Shop


class Feature(StrEnum):
    RE_ANALYSIS = "re_analysis"
    HISTORICAL_WEEKS = "historical_weeks"
    MULTI_SHOP = "multi_shop"
    ZALO_PUSH = "zalo_push"
    BENCHMARKS = "benchmarks"
    CSV_EXPORT = "csv_export"
    CREATOR_CRM = "creator_crm"
    SHOPEE_LAZADA = "shopee_lazada"
    AI_CALLS_PER_IMPORT = "ai_calls_per_import"


TIER_GATES: dict[str, dict] = {
    "pro_trial": {  # P4-2: 14-day trial = pro features
        Feature.RE_ANALYSIS: True,
        Feature.HISTORICAL_WEEKS: 12,
        Feature.MULTI_SHOP: 3,
        Feature.ZALO_PUSH: True,
        Feature.BENCHMARKS: True,
        Feature.CSV_EXPORT: True,
        Feature.CREATOR_CRM: "basic",
        Feature.SHOPEE_LAZADA: True,
        Feature.AI_CALLS_PER_IMPORT: 10,
    },
    "free": {
        Feature.RE_ANALYSIS: False,
        Feature.HISTORICAL_WEEKS: 4,
        Feature.MULTI_SHOP: 1,
        Feature.ZALO_PUSH: False,
        Feature.BENCHMARKS: False,
        Feature.CSV_EXPORT: False,
        Feature.CREATOR_CRM: False,
        Feature.SHOPEE_LAZADA: True,
        Feature.AI_CALLS_PER_IMPORT: 5,
    },
    "pro": {
        Feature.RE_ANALYSIS: True,
        Feature.HISTORICAL_WEEKS: 12,
        Feature.MULTI_SHOP: 3,
        Feature.ZALO_PUSH: True,
        Feature.BENCHMARKS: True,
        Feature.CSV_EXPORT: True,
        Feature.CREATOR_CRM: "basic",
        Feature.SHOPEE_LAZADA: True,
        Feature.AI_CALLS_PER_IMPORT: 10,
    },
    "business": {
        Feature.RE_ANALYSIS: True,
        Feature.HISTORICAL_WEEKS: 52,
        Feature.MULTI_SHOP: 999,
        Feature.ZALO_PUSH: True,
        Feature.BENCHMARKS: True,
        Feature.CSV_EXPORT: True,
        Feature.CREATOR_CRM: "full",
        Feature.SHOPEE_LAZADA: True,
        Feature.AI_CALLS_PER_IMPORT: 15,
    },
}

UPGRADE_MESSAGES: dict[Feature, str] = {
    Feature.RE_ANALYSIS: "Tính lại P&L với COGS mới cần gói Pro (99k/tháng).",
    Feature.HISTORICAL_WEEKS: "Xem lịch sử quá 4 tuần cần gói Pro (99k/tháng).",
    Feature.ZALO_PUSH: "Nhận thông báo Zalo hàng tuần cần gói Pro (99k/tháng).",
    Feature.CSV_EXPORT: "Xuất dữ liệu CSV cần gói Pro (99k/tháng).",
    Feature.SHOPEE_LAZADA: "Import dữ liệu Shopee/Lazada không khả dụng ở gói này.",
    Feature.CREATOR_CRM: "Creator CRM cần gói Pro (99k/tháng).",
    Feature.BENCHMARKS: "Benchmark ngành cần gói Pro (99k/tháng).",
}


def get_gate_value(shop: Shop, feature: Feature):
    """Get the feature gate value for the shop's tier. Returns False/0 if not available."""
    tier = getattr(shop, "subscription_tier", "free") or "free"
    gates = TIER_GATES.get(tier, TIER_GATES["free"])
    return gates.get(feature, False)


def require_feature(shop: Shop, feature: Feature) -> None:
    """Raise HTTP 402 if shop's tier doesn't include the feature."""
    value = get_gate_value(shop, feature)
    if value is False or value == 0:
        msg = UPGRADE_MESSAGES.get(
            feature, "Tính năng này cần gói cao hơn. Nâng cấp tại /settings/billing."
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": {
                    "code": "FEATURE_LOCKED",
                    "message": msg,
                    "feature": feature.value,
                    "upgrade_url": "/settings/billing",
                }
            },
        )


def get_ai_calls_limit(shop: Shop) -> int:
    """Return AI calls per import based on tier."""
    val = get_gate_value(shop, Feature.AI_CALLS_PER_IMPORT)
    return int(val) if isinstance(val, (int, float)) else 3


def get_history_weeks_limit(shop: Shop) -> int:
    """Return max historical weeks to show based on tier."""
    val = get_gate_value(shop, Feature.HISTORICAL_WEEKS)
    return int(val) if isinstance(val, (int, float)) else 4
