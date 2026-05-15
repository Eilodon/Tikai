"""
Demo API — static InsightSnapshot for the public /demo page.
No auth, no DB reads. Data is hardcoded to show Tikai's capabilities.
"""

from fastapi import APIRouter, Request

from app.core.rate_limit import limiter

router = APIRouter()

_DEMO_SNAPSHOT = {
    "id": "00000000-0000-0000-0000-000000000001",
    "shop_id": "00000000-0000-0000-0000-000000000002",
    "period_start": "2026-05-01",
    "period_end": "2026-05-14",
    "gmv_total": "420000000",
    "net_revenue": "28350000",
    "total_orders": 1247,
    "total_refunds": 52,
    "refund_rate": "0.0417",
    "cash_in_14d": "38200000",
    "cash_in_30d": "71400000",
    "cash_pending_total": "14500000",
    "top_leaks": [
        {
            "type": "sku",
            "id": "sku-001",
            "name": "Kem dưỡng ẩm 50ml",
            "estimated_loss": "12600000",
            "reason": "affiliate_high",
            "confidence": "high",
            "can_act_now": True,
        },
        {
            "type": "creator",
            "id": "creator-001",
            "name": "KOC Nguyễn Minh A",
            "estimated_loss": "8400000",
            "reason": "commission_exceeds_margin",
            "confidence": "high",
            "can_act_now": True,
        },
        {
            "type": "sku",
            "id": "sku-002",
            "name": "Serum Vitamin C 30ml",
            "estimated_loss": "5200000",
            "reason": "voucher_high",
            "confidence": "medium",
            "can_act_now": True,
        },
    ],
    "top_skus": [
        {
            "sku_id": "sku-001",
            "sku_name": "Kem dưỡng ẩm 50ml",
            "gmv": "186000000",
            "net_revenue": "8370000",
            "order_count": 620,
            "total_quantity": 620,
            "refund_rate": "0.032",
            "margin_pct": "-0.042",
            "margin": "-7812000",
            "gmv_rank": 1,
            "affiliate_commission": "37200000",
            "voucher_cost": "9300000",
            "health_status": "critical",
            "health_reasons": ["margin âm", "affiliate rate 20%"],
        },
        {
            "sku_id": "sku-002",
            "sku_name": "Serum Vitamin C 30ml",
            "gmv": "126000000",
            "net_revenue": "12600000",
            "order_count": 420,
            "total_quantity": 420,
            "refund_rate": "0.048",
            "margin_pct": "0.051",
            "margin": "6426000",
            "gmv_rank": 2,
            "affiliate_commission": "12600000",
            "voucher_cost": "18900000",
            "health_status": "warning",
            "health_reasons": ["voucher rate cao 15%"],
        },
        {
            "sku_id": "sku-003",
            "sku_name": "Tẩy trang micellar 200ml",
            "gmv": "108000000",
            "net_revenue": "18360000",
            "order_count": 360,
            "total_quantity": 360,
            "refund_rate": "0.028",
            "margin_pct": "0.142",
            "margin": "15336000",
            "gmv_rank": 3,
            "affiliate_commission": "5400000",
            "voucher_cost": "3240000",
            "health_status": "healthy",
            "health_reasons": [],
        },
    ],
    "top_creators": [
        {
            "creator_id": "c-001",
            "creator_name": "KOC Nguyễn Minh A",
            "attributed_gmv": "84000000",
            "attributed_net_revenue": "5460000",
            "total_commission": "16800000",
            "order_count": 280,
            "revenue_efficiency": "0.325",
            "performance_label": "losing",
            "suggested_max_commission_rate": "0.065",
        },
        {
            "creator_id": "c-002",
            "creator_name": "Beauty Reviewer B",
            "attributed_gmv": "63000000",
            "attributed_net_revenue": "14490000",
            "total_commission": "6300000",
            "order_count": 210,
            "revenue_efficiency": "2.3",
            "performance_label": "star",
            "suggested_max_commission_rate": None,
        },
    ],
    "action_triggers": [],
    "is_net_revenue_mode": False,
    "cogs_coverage_pct": "0.67",
    "rule_engine_version": "v2.1.0",
    "fee_config_version": "2026-VN-v3",
    "days_in_period": 14,
    "is_partial_period": False,
    "is_first_import": False,
    "created_at": "2026-05-14T08:00:00+00:00",
}


@router.get("/demo/snapshot")
@limiter.limit("60/minute")
async def get_demo_snapshot(request: Request):
    """Public demo snapshot — no auth required. Rate limited to 60/min/IP."""
    return _DEMO_SNAPSHOT
