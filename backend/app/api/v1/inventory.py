"""
Inventory Tracking API — stock levels + days-to-stockout per SKU.
v2.3.0: Pro+ feature. Stores stock_on_hand in shop.stock_map JSONB.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.gates import Feature, require_feature
from app.core.rate_limit import limiter
from app.models.order import Order
from app.models.shop import Shop

router = APIRouter()
log = structlog.get_logger()

_LOOKBACK_DAYS = 30
_CRITICAL_DAYS = 7
_WARNING_DAYS = 14


class StockSetRequest(BaseModel):
    sku_id: str = Field(..., min_length=1, max_length=100)
    stock_on_hand: int = Field(..., ge=0)


class StockSetResponse(BaseModel):
    sku_id: str
    stock_on_hand: int


class SKUStockStatus(BaseModel):
    sku_id: str
    sku_name: str
    stock_on_hand: int | None
    units_sold_30d: int
    avg_daily_units: float
    days_to_stockout: float | None
    status: str  # "critical" | "warning" | "ok" | "no_stock_data" | "no_sales"


@router.post("/inventory/set-stock")
@limiter.limit("60/hour")
async def set_stock(
    request: Request,
    body: StockSetRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StockSetResponse:
    """Set current stock level for a SKU. Pro+ only."""
    require_feature(shop, Feature.INVENTORY_TRACKING)

    current_map: dict = shop.stock_map or {}
    current_map[body.sku_id] = body.stock_on_hand

    from sqlalchemy import update

    await db.execute(update(Shop).where(Shop.id == shop.id).values(stock_map=current_map))
    await db.commit()

    log.info(
        "inventory.stock_set", shop_id=str(shop.id), sku_id=body.sku_id, stock=body.stock_on_hand
    )
    return StockSetResponse(sku_id=body.sku_id, stock_on_hand=body.stock_on_hand)


@router.delete("/inventory/set-stock/{sku_id}")
@limiter.limit("60/hour")
async def remove_stock(
    request: Request,
    sku_id: str,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Remove stock entry for a SKU."""
    require_feature(shop, Feature.INVENTORY_TRACKING)

    current_map: dict = dict(shop.stock_map or {})
    if sku_id not in current_map:
        raise HTTPException(
            404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Không có dữ liệu tồn kho cho SKU '{sku_id}'.",
                }
            },
        )

    del current_map[sku_id]

    from sqlalchemy import update

    await db.execute(update(Shop).where(Shop.id == shop.id).values(stock_map=current_map))
    await db.commit()
    return {"deleted": sku_id}


@router.get("/inventory/status")
async def get_inventory_status(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SKUStockStatus]:
    """
    Return per-SKU inventory status: stock_on_hand, avg daily units, days to stockout.
    Only returns SKUs with stock data set OR with sales in last 30 days.
    """
    require_feature(shop, Feature.INVENTORY_TRACKING)

    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=_LOOKBACK_DAYS)

    # Aggregate units sold + sku_name per SKU in last 30 days
    rows = await db.execute(
        select(
            Order.sku_id,
            Order.sku_name,
            func.sum(Order.quantity).label("total_qty"),
        )
        .where(
            Order.shop_id == shop.id,
            Order.order_date >= cutoff,
            Order.status.not_in(["cancelled", "returned", "refunded"]),
        )
        .group_by(Order.sku_id, Order.sku_name)
    )
    sales_by_sku: dict[str, dict] = {
        r.sku_id: {"sku_name": r.sku_name, "total_qty": int(r.total_qty or 0)} for r in rows
    }

    stock_map: dict = shop.stock_map or {}

    # Union of SKUs with stock data or with recent sales
    all_sku_ids = set(stock_map.keys()) | set(sales_by_sku.keys())
    if not all_sku_ids:
        return []

    result: list[SKUStockStatus] = []
    for sku_id in sorted(all_sku_ids):
        sales_info = sales_by_sku.get(sku_id, {})
        units_sold_30d = sales_info.get("total_qty", 0)
        sku_name = sales_info.get("sku_name", sku_id)
        avg_daily = units_sold_30d / _LOOKBACK_DAYS

        stock_on_hand: int | None = stock_map.get(sku_id)

        if stock_on_hand is None:
            days_to_stockout = None
            status = "no_stock_data"
        elif avg_daily <= 0:
            days_to_stockout = None
            status = "no_sales"
        else:
            days_to_stockout = round(stock_on_hand / avg_daily, 1)
            if days_to_stockout <= _CRITICAL_DAYS:
                status = "critical"
            elif days_to_stockout <= _WARNING_DAYS:
                status = "warning"
            else:
                status = "ok"

        result.append(
            SKUStockStatus(
                sku_id=sku_id,
                sku_name=sku_name,
                stock_on_hand=stock_on_hand,
                units_sold_30d=units_sold_30d,
                avg_daily_units=round(avg_daily, 2),
                days_to_stockout=days_to_stockout,
                status=status,
            )
        )

    # Sort: critical first, then warning, then by days_to_stockout asc
    _order = {"critical": 0, "warning": 1, "ok": 2, "no_stock_data": 3, "no_sales": 4}
    result.sort(key=lambda x: (_order.get(x.status, 9), x.days_to_stockout or float("inf")))
    return result
