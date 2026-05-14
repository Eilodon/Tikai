"""
Live Stream Cost Tracking API.
Unique Tikai feature — no competitor tracks live stream ROI for VN sellers.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.models.livestream import LiveStreamSession
from app.models.shop import Shop

router = APIRouter()


class LiveStreamCreateRequest(BaseModel):
    livestream_date: date
    duration_minutes: int = Field(0, ge=0, le=1440)  # max 24h
    # FIX MED-V2-6: prevent negative costs (would inflate ROI fraudulently)
    host_cost: Decimal = Field(Decimal("0"), ge=0)
    studio_cost: Decimal = Field(Decimal("0"), ge=0)
    product_sample_cost: Decimal = Field(Decimal("0"), ge=0)
    ads_cost: Decimal = Field(Decimal("0"), ge=0)
    other_cost: Decimal = Field(Decimal("0"), ge=0)
    notes: str | None = Field(None, max_length=500)


class LiveStreamUpdateResultRequest(BaseModel):
    attributed_gmv: Decimal | None = Field(None, ge=0)
    attributed_orders: int | None = Field(None, ge=0)
    attributed_net_revenue: Decimal | None = None  # can be negative (fees > GMV)


class LiveStreamResponse(BaseModel):
    id: uuid.UUID
    livestream_date: date
    duration_minutes: int
    host_cost: Decimal
    studio_cost: Decimal
    product_sample_cost: Decimal
    ads_cost: Decimal
    other_cost: Decimal
    total_cost: Decimal
    attributed_gmv: Decimal | None
    attributed_orders: int
    attributed_net_revenue: Decimal | None
    live_roi: Decimal | None
    net_roi: Decimal | None
    notes: str | None


def _to_response(ls: LiveStreamSession) -> LiveStreamResponse:
    return LiveStreamResponse(
        id=ls.id,
        livestream_date=ls.livestream_date,
        duration_minutes=ls.duration_minutes,
        host_cost=ls.host_cost,
        studio_cost=ls.studio_cost,
        product_sample_cost=ls.product_sample_cost,
        ads_cost=ls.ads_cost,
        other_cost=ls.other_cost,
        total_cost=ls.total_cost,
        attributed_gmv=ls.attributed_gmv,
        attributed_orders=ls.attributed_orders,
        attributed_net_revenue=ls.attributed_net_revenue,
        live_roi=ls.live_roi,
        net_roi=ls.net_roi,
        notes=ls.notes,
    )


@router.get("/livestream")
async def list_livestreams(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LiveStreamResponse]:
    rows = await db.scalars(
        select(LiveStreamSession)
        .where(LiveStreamSession.shop_id == shop.id)
        .order_by(LiveStreamSession.livestream_date.desc())
        .limit(20)
    )
    return [_to_response(r) for r in rows]


@router.post("/livestream", status_code=201)
async def create_livestream(
    body: LiveStreamCreateRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LiveStreamResponse:
    ls = LiveStreamSession(shop_id=shop.id, **body.model_dump())
    db.add(ls)
    await db.flush()
    await db.refresh(ls)
    # F-3-04: removed explicit db.commit() — get_db() auto-commits on yield exit
    return _to_response(ls)


@router.patch("/livestream/{livestream_id}/results")
async def update_livestream_results(
    livestream_id: uuid.UUID,
    body: LiveStreamUpdateResultRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LiveStreamResponse:
    ls = await db.scalar(
        select(LiveStreamSession).where(
            LiveStreamSession.id == livestream_id,
            LiveStreamSession.shop_id == shop.id,
        )
    )
    if not ls:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(ls, field, val)

    await db.flush()
    # F-3-04: removed explicit db.commit() — get_db() auto-commits
    return _to_response(ls)


@router.delete("/livestream/{livestream_id}", status_code=204)
async def delete_livestream(
    livestream_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    ls = await db.scalar(
        select(LiveStreamSession).where(
            LiveStreamSession.id == livestream_id,
            LiveStreamSession.shop_id == shop.id,
        )
    )
    if not ls:
        raise HTTPException(404)
    await db.delete(ls)
    # F-3-04: removed explicit db.commit() — get_db() auto-commits
