"""
Tools API — calculator utilities: Price Recommender + What-If Simulator.
INVARIANT: pure computation endpoints — no DB writes, no AI calls.
"""
import uuid
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.models.fee_config import FeeConfig
from app.models.insight_snapshot import InsightSnapshot
from app.models.shop import Shop
from app.schemas.insight import SKUSummaryItem
from app.services.rule_engine.fee_calculator import FeeConfigData
from app.services.rule_engine.price_recommender import recommend_price
from app.services.rule_engine.simulator import SimulatorParams, simulate_sku

router = APIRouter()
log = structlog.get_logger()


def _safe_parse_tools(schema_class, items: list) -> list:
    result = []
    for item in items:
        try:
            result.append(schema_class(**item))
        except Exception:
            pass
    return result


async def _get_latest_fee_config_data(
    db: AsyncSession, platform: str = "tiktok"
) -> FeeConfigData:
    config = await db.scalar(
        select(FeeConfig)
        .where(FeeConfig.platform == platform)
        .order_by(FeeConfig.effective_from.desc())
        .limit(1)
    )
    if not config:
        raise HTTPException(
            422,
            detail={"error": {"code": "FEE_CONFIG_MISSING", "message": "Không tìm thấy cấu hình phí."}},
        )
    return FeeConfigData(
        version=config.version,
        platform_commission_rate=config.platform_commission_rate,
        transaction_fee_rate=config.transaction_fee_rate,
        order_processing_fee_per_order=config.order_processing_fee_per_order,
    )


# ── Price Recommender ─────────────────────────────────────────────────────────

class PriceRecommendRequest(BaseModel):
    cogs_per_unit: Decimal
    target_margin_pct: Decimal   # 0.05 → 0.50
    affiliate_rate: Decimal = Decimal("0.10")
    voucher_rate: Decimal = Decimal("0.05")


@router.post("/tools/price-recommend")
async def price_recommend(
    body: PriceRecommendRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Reverse P&L: từ COGS + desired margin → giá bán tối thiểu.
    Phí sàn lấy từ FeeConfig hiện tại của platform.
    """
    fee_config = await _get_latest_fee_config_data(db)
    try:
        result = recommend_price(
            cogs_per_unit=body.cogs_per_unit,
            target_margin_pct=body.target_margin_pct,
            platform_commission_rate=fee_config.platform_commission_rate,
            transaction_fee_rate=fee_config.transaction_fee_rate,
            order_processing_fee=fee_config.order_processing_fee_per_order,
            affiliate_rate=body.affiliate_rate,
            voucher_rate=body.voucher_rate,
        )
    except ValueError as e:
        raise HTTPException(
            422,
            detail={"error": {"code": "INFEASIBLE_MARGIN", "message": str(e)}},
        )

    log.info(
        "tools.price_recommend",
        shop_id=str(shop.id),
        cogs=str(body.cogs_per_unit),
        target_margin=str(body.target_margin_pct),
        min_price=str(result.min_price),
    )
    return {
        "min_price": str(result.min_price),
        "target_margin_pct": str(result.target_margin_pct),
        "actual_margin_pct": str(result.actual_margin_pct),
        "breakdown": {k: str(v) for k, v in result.breakdown.items()},
        "warning": result.warning,
        "fee_config_version": fee_config.version,
    }


# ── What-If Simulator ─────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    snapshot_id: uuid.UUID
    sku_id: str
    affiliate_rate: Decimal | None = None
    voucher_rate: Decimal | None = None
    price_change_pct: Decimal | None = None


@router.post("/tools/simulate")
async def simulate(
    body: SimulateRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Re-run P&L cho 1 SKU với params giả định.
    INVARIANT: không write vào DB — chỉ tính in-memory.
    """
    snapshot = await db.scalar(
        select(InsightSnapshot).where(
            InsightSnapshot.id == body.snapshot_id,
            InsightSnapshot.shop_id == shop.id,  # shop isolation
        )
    )
    if not snapshot:
        raise HTTPException(
            404,
            detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy snapshot."}},
        )

    top_skus = _safe_parse_tools(SKUSummaryItem, snapshot.top_skus_json or [])
    sku = next((s for s in top_skus if s.sku_id == body.sku_id), None)
    if not sku:
        raise HTTPException(
            404,
            detail={"error": {"code": "SKU_NOT_FOUND", "message": "SKU không có trong snapshot."}},
        )

    raw_cogs = shop.cogs_map or {}
    cogs_per_unit = (
        Decimal(str(raw_cogs[body.sku_id]))
        if body.sku_id in raw_cogs
        else None
    )

    fee_config = await _get_latest_fee_config_data(db)
    params = SimulatorParams(
        affiliate_rate=body.affiliate_rate,
        voucher_rate=body.voucher_rate,
        price_change_pct=body.price_change_pct,
    )
    result = simulate_sku(sku.model_dump(), params, fee_config, cogs_per_unit)

    return {
        "current_net_revenue": str(result.current_net_revenue),
        "current_margin": str(result.current_margin) if result.current_margin is not None else None,
        "current_margin_pct": str(result.current_margin_pct) if result.current_margin_pct is not None else None,
        "simulated_net_revenue": str(result.simulated_net_revenue),
        "simulated_margin": str(result.simulated_margin) if result.simulated_margin is not None else None,
        "simulated_margin_pct": str(result.simulated_margin_pct) if result.simulated_margin_pct is not None else None,
        "net_revenue_delta": str(result.net_revenue_delta),
        "margin_delta": str(result.margin_delta) if result.margin_delta is not None else None,
        "breakeven_extra_orders": result.breakeven_extra_orders,
        "verdict": result.verdict,
    }
