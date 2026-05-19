"""
Tools API — calculator utilities: Price Recommender + What-If Simulator + Campaign Pre-Check.
INVARIANT: pure computation endpoints — no DB writes, no AI calls.
"""

import uuid
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.rate_limit import limiter
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


async def _get_latest_fee_config_data(db: AsyncSession, platform: str = "tiktok") -> FeeConfigData:
    config = await db.scalar(
        select(FeeConfig)
        .where(FeeConfig.platform == platform)
        .order_by(FeeConfig.effective_from.desc())
        .limit(1)
    )
    if not config:
        raise HTTPException(
            422,
            detail={
                "error": {"code": "FEE_CONFIG_MISSING", "message": "Không tìm thấy cấu hình phí."}
            },
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
    # BUG-H2 FIX: negative rates / >100% margins violated min_price >= cogs invariant.
    target_margin_pct: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("0.99"))
    affiliate_rate: Decimal = Field(Decimal("0.10"), ge=Decimal("0"), le=Decimal("0.50"))
    voucher_rate: Decimal = Field(Decimal("0.05"), ge=Decimal("0"), le=Decimal("0.50"))


@router.post("/tools/price-recommend")
@limiter.limit("120/hour")
async def price_recommend(
    request: Request,
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


# ── Fee Schedule (public, no auth) ───────────────────────────────────────────


@router.get("/tools/fee-schedule/public")
@limiter.limit("30/minute")
async def get_fee_schedule_public(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return current TikTok Shop fee rates for public calculator. No auth required."""
    fee_config = await _get_latest_fee_config_data(db)
    return {
        "version": fee_config.version,
        "platform_commission_rate": str(fee_config.platform_commission_rate),
        "transaction_fee_rate": str(fee_config.transaction_fee_rate),
        "order_processing_fee_per_order": str(fee_config.order_processing_fee_per_order),
    }


# ── Fee Config Current (Gap #1) ──────────────────────────────────────────────


@router.get("/fee-config/current")
@limiter.limit("60/minute")
async def get_current_fee_config(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Gap #1 fix: Return full fee config for the shop's current version,
    including verified_date and effective_to so UI can show fee policy badge
    and warn when fee policy needs renewal.
    """
    from datetime import date

    config = await db.scalar(
        select(FeeConfig)
        .where(
            FeeConfig.platform == "tiktok",
            FeeConfig.version == shop.fee_config_version,
        )
        .limit(1)
    )
    if not config:
        # Fall back to latest if version string not found
        config = await db.scalar(
            select(FeeConfig)
            .where(FeeConfig.platform == "tiktok")
            .order_by(FeeConfig.effective_from.desc())
            .limit(1)
        )
    if not config:
        raise HTTPException(
            404,
            detail={
                "error": {"code": "FEE_CONFIG_NOT_FOUND", "message": "Không tìm thấy cấu hình phí."}
            },
        )

    today = date.today()
    is_stale = config.effective_to is not None and config.effective_to < today

    return {
        "version": config.version,
        "platform": config.platform,
        "platform_commission_rate": str(config.platform_commission_rate),
        "transaction_fee_rate": str(config.transaction_fee_rate),
        "order_processing_fee_per_order": str(config.order_processing_fee_per_order),
        "effective_from": config.effective_from.isoformat(),
        "effective_to": config.effective_to.isoformat() if config.effective_to else None,
        "verified_date": config.verified_date.isoformat(),
        "notes": config.notes,
        "is_stale": is_stale,
    }


# ── Price Recommender (public, no auth, rate-limited by IP) ──────────────────


@router.post("/tools/price-recommend/public")
@limiter.limit("30/hour")
async def price_recommend_public(
    request: Request,
    body: PriceRecommendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Public price calculator — no auth required. Rate limited to 30 calls/hour/IP."""
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
    affiliate_rate: Decimal | None = Field(None, ge=Decimal("0"), le=Decimal("0.50"))
    voucher_rate: Decimal | None = Field(None, ge=Decimal("0"), le=Decimal("0.50"))
    price_change_pct: Decimal | None = Field(None, ge=Decimal("-0.5"), le=Decimal("0.5"))


@router.post("/tools/simulate")
@limiter.limit("60/hour")
async def simulate(
    request: Request,
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
    cogs_per_unit = Decimal(str(raw_cogs[body.sku_id])) if body.sku_id in raw_cogs else None

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
        "current_margin_pct": str(result.current_margin_pct)
        if result.current_margin_pct is not None
        else None,
        "simulated_net_revenue": str(result.simulated_net_revenue),
        "simulated_margin": str(result.simulated_margin)
        if result.simulated_margin is not None
        else None,
        "simulated_margin_pct": str(result.simulated_margin_pct)
        if result.simulated_margin_pct is not None
        else None,
        "net_revenue_delta": str(result.net_revenue_delta),
        "margin_delta": str(result.margin_delta) if result.margin_delta is not None else None,
        "breakeven_extra_orders": result.breakeven_extra_orders,
        "verdict": result.verdict,
    }


# ── Campaign Pre-Check (multi-SKU) ───────────────────────────────────────────


class CampaignSKUInput(BaseModel):
    sku_id: str
    planned_units: int = Field(..., gt=0, le=100_000)
    price_change_pct: Decimal = Field(Decimal("0"), ge=Decimal("-0.5"), le=Decimal("0.5"))
    affiliate_rate: Decimal | None = Field(None, ge=Decimal("0"), le=Decimal("0.50"))
    voucher_rate: Decimal | None = Field(None, ge=Decimal("0"), le=Decimal("0.50"))


class SimulateCampaignRequest(BaseModel):
    snapshot_id: uuid.UUID
    skus: list[CampaignSKUInput] = Field(..., min_length=1, max_length=50)


@router.post("/tools/simulate-campaign")
@limiter.limit("20/hour")
async def simulate_campaign(
    request: Request,
    body: SimulateCampaignRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Multi-SKU campaign pre-check: project net revenue + margin for a planned campaign.

    Each SKU entry specifies planned_units and optional rate overrides.
    Returns per-SKU simulation plus portfolio-level totals.
    INVARIANT: no DB writes — pure in-memory calculation.
    """
    snapshot = await db.scalar(
        select(InsightSnapshot).where(
            InsightSnapshot.id == body.snapshot_id,
            InsightSnapshot.shop_id == shop.id,
        )
    )
    if not snapshot:
        raise HTTPException(
            404,
            detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy snapshot."}},
        )

    top_skus = _safe_parse_tools(SKUSummaryItem, snapshot.top_skus_json or [])
    sku_index = {s.sku_id: s for s in top_skus}
    fee_config = await _get_latest_fee_config_data(db)
    raw_cogs = shop.cogs_map or {}

    sku_results = []
    total_current_nr = Decimal("0")
    total_simulated_nr = Decimal("0")
    total_current_margin = Decimal("0")
    total_simulated_margin = Decimal("0")
    has_margin = True

    for entry in body.skus:
        sku = sku_index.get(entry.sku_id)
        if not sku:
            raise HTTPException(
                404,
                detail={
                    "error": {
                        "code": "SKU_NOT_FOUND",
                        "message": f"SKU {entry.sku_id} không có trong snapshot.",
                    }
                },
            )

        cogs_per_unit = Decimal(str(raw_cogs[entry.sku_id])) if entry.sku_id in raw_cogs else None

        # Scale snapshot metrics to planned_units
        snapshot_units = max(sku.total_quantity, 1)
        scale = Decimal(entry.planned_units) / Decimal(snapshot_units)
        scaled_snapshot = {
            **sku.model_dump(),
            "gmv": str(sku.gmv * scale),
            "net_revenue": str(sku.net_revenue * scale),
            "affiliate_commission": str(sku.affiliate_commission * scale),
            "voucher_cost": str(sku.voucher_cost * scale),
            "order_count": max(1, int(Decimal(str(sku.order_count)) * scale)),
            "total_quantity": entry.planned_units,
        }

        params = SimulatorParams(
            affiliate_rate=entry.affiliate_rate,
            voucher_rate=entry.voucher_rate,
            price_change_pct=entry.price_change_pct if entry.price_change_pct != 0 else None,
        )
        result = simulate_sku(scaled_snapshot, params, fee_config, cogs_per_unit)

        total_current_nr += result.current_net_revenue
        total_simulated_nr += result.simulated_net_revenue
        if result.current_margin is not None and result.simulated_margin is not None:
            total_current_margin += result.current_margin
            total_simulated_margin += result.simulated_margin
        else:
            has_margin = False

        sku_results.append(
            {
                "sku_id": entry.sku_id,
                "sku_name": sku.sku_name,
                "planned_units": entry.planned_units,
                "current_net_revenue": str(result.current_net_revenue),
                "simulated_net_revenue": str(result.simulated_net_revenue),
                "net_revenue_delta": str(result.net_revenue_delta),
                "current_margin": str(result.current_margin)
                if result.current_margin is not None
                else None,
                "simulated_margin": str(result.simulated_margin)
                if result.simulated_margin is not None
                else None,
                "simulated_margin_pct": str(result.simulated_margin_pct)
                if result.simulated_margin_pct is not None
                else None,
                "verdict": result.verdict,
            }
        )

    portfolio_margin_delta = (total_simulated_margin - total_current_margin) if has_margin else None
    log.info(
        "tools.simulate_campaign",
        shop_id=str(shop.id),
        snapshot_id=str(body.snapshot_id),
        sku_count=len(body.skus),
    )
    return {
        "snapshot_id": str(body.snapshot_id),
        "fee_config_version": fee_config.version,
        "skus": sku_results,
        "portfolio": {
            "total_current_net_revenue": str(total_current_nr),
            "total_simulated_net_revenue": str(total_simulated_nr),
            "total_net_revenue_delta": str(total_simulated_nr - total_current_nr),
            "total_current_margin": str(total_current_margin) if has_margin else None,
            "total_simulated_margin": str(total_simulated_margin) if has_margin else None,
            "total_margin_delta": str(portfolio_margin_delta)
            if portfolio_margin_delta is not None
            else None,
        },
    }
