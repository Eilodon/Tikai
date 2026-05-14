"""
COGS API — seller inputs cost-of-goods per SKU.
FIX QUAL-05: uses ORM-style update via mapped column, not raw text() SQL.
v1.0.0: Rate limiting on POST + result cap on GET (was unbounded for shops with 1000+ SKUs).
"""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.order import Order
from app.models.shop import Shop

router = APIRouter()

# Cap: any shop with more than 500 distinct SKUs is extraordinary;
# returning more would degrade the settings UI without adding value.
MAX_COGS_SKUS = 500


class COGSItem(BaseModel):
    sku_id: str
    sku_name: str
    cogs_per_unit: Decimal = Field(..., gt=0, description="Cost per unit in VND")


class COGSBatchRequest(BaseModel):
    items: list[COGSItem]


class COGSItemResponse(BaseModel):
    sku_id: str
    sku_name: str
    cogs_per_unit: str  # string to preserve Decimal precision


class COGSBatchResponse(BaseModel):
    updated: int
    items: list[COGSItemResponse]
    total_skus: int = 0   # v1.0.0: inform frontend if results were capped


@router.get("/cogs")
async def get_cogs(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSBatchResponse:
    """Get COGS for all SKUs this shop has ever imported.
    v1.0.0: Capped at MAX_COGS_SKUS (500) — unbounded query could return thousands
    of rows for high-volume shops and degrade the settings page load time.
    """
    result = await db.execute(
        select(Order.sku_id, Order.sku_name)
        .where(Order.shop_id == shop.id)
        .distinct()
        .order_by(Order.sku_name)
        .limit(MAX_COGS_SKUS)
    )
    sku_rows = result.fetchall()
    cogs_map: dict = shop.cogs_map or {}

    items = [
        COGSItemResponse(
            sku_id=row.sku_id,
            sku_name=row.sku_name,
            cogs_per_unit=str(cogs_map.get(row.sku_id, "0")),
        )
        for row in sku_rows
    ]
    return COGSBatchResponse(updated=0, items=items, total_skus=len(items))


@router.post("/cogs")
@limiter.limit("30/hour")   # v1.0.0: prevent repeated JSONB writes on shop record
async def upsert_cogs(
    request: Request,
    body: COGSBatchRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSBatchResponse:
    """Upsert COGS for multiple SKUs.
    FIX QUAL-05: uses shop.cogs_map ORM column directly.
    """
    current: dict = dict(shop.cogs_map or {})
    for item in body.items:
        current[item.sku_id] = str(item.cogs_per_unit)

    shop.cogs_map = current
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(shop, "cogs_map")
    await db.flush()

    return COGSBatchResponse(
        updated=len(body.items),
        items=[
            COGSItemResponse(
                sku_id=i.sku_id,
                sku_name=i.sku_name,
                cogs_per_unit=str(i.cogs_per_unit),
            )
            for i in body.items
        ],
        total_skus=len(body.items),
    )
