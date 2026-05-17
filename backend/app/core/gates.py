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
    INVENTORY_TRACKING = "inventory_tracking"
    MCN_AGGREGATE = "mcn_aggregate"
    MISA_EXPORT = "misa_export"


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
        Feature.INVENTORY_TRACKING: True,
        Feature.MCN_AGGREGATE: False,
        Feature.MISA_EXPORT: True,
    },
    "free": {
        Feature.RE_ANALYSIS: False,
        Feature.HISTORICAL_WEEKS: 4,
        Feature.MULTI_SHOP: 1,
        Feature.ZALO_PUSH: False,
        Feature.BENCHMARKS: False,
        Feature.CSV_EXPORT: False,
        Feature.CREATOR_CRM: False,
        Feature.SHOPEE_LAZADA: False,
        Feature.AI_CALLS_PER_IMPORT: 5,
        Feature.INVENTORY_TRACKING: False,
        Feature.MCN_AGGREGATE: False,
        Feature.MISA_EXPORT: False,
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
        Feature.INVENTORY_TRACKING: True,
        Feature.MCN_AGGREGATE: False,
        Feature.MISA_EXPORT: True,
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
        Feature.INVENTORY_TRACKING: True,
        Feature.MCN_AGGREGATE: True,
        Feature.MISA_EXPORT: True,
    },
    # v2.3.0: Enterprise tier for MCN / multi-agency accounts (2–5M VND/tháng)
    "enterprise": {
        Feature.RE_ANALYSIS: True,
        Feature.HISTORICAL_WEEKS: 104,  # 2 years
        Feature.MULTI_SHOP: 9999,
        Feature.ZALO_PUSH: True,
        Feature.BENCHMARKS: True,
        Feature.CSV_EXPORT: True,
        Feature.CREATOR_CRM: "full",
        Feature.SHOPEE_LAZADA: True,
        Feature.AI_CALLS_PER_IMPORT: 20,
        Feature.INVENTORY_TRACKING: True,
        Feature.MCN_AGGREGATE: True,
        Feature.MISA_EXPORT: True,
    },
}

UPGRADE_MESSAGES: dict[Feature, str] = {
    Feature.RE_ANALYSIS: "Tính lại P&L với COGS mới cần gói Pro (299k/tháng).",
    Feature.HISTORICAL_WEEKS: "Xem lịch sử quá 4 tuần cần gói Pro (299k/tháng).",
    Feature.ZALO_PUSH: "Nhận thông báo Zalo hàng tuần cần gói Pro (299k/tháng).",
    Feature.CSV_EXPORT: "Xuất dữ liệu CSV cần gói Pro (299k/tháng).",
    Feature.SHOPEE_LAZADA: "Import dữ liệu Shopee/Lazada cần gói Pro (299k/tháng).",
    Feature.CREATOR_CRM: "Creator CRM cần gói Pro (299k/tháng).",
    Feature.BENCHMARKS: "Benchmark ngành cần gói Pro (299k/tháng).",
    Feature.INVENTORY_TRACKING: "Theo dõi tồn kho và dự báo hết hàng cần gói Pro (299k/tháng).",
    Feature.MCN_AGGREGATE: "Xem tổng hợp đa shop cần gói Business (799k/tháng).",
    Feature.MISA_EXPORT: "Xuất báo cáo theo chuẩn Misa cần gói Pro (299k/tháng).",
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
