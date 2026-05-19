"""
Creator CRM API.
Gated: Feature.CREATOR_CRM (pro/business).
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.gates import Feature, get_gate_value
from app.core.rate_limit import limiter
from app.models.commission_snapshot import CommissionSnapshot
from app.models.creator_profile import CreatorProfile
from app.models.insight_snapshot import InsightSnapshot
from app.models.shop import Shop
from app.services.creators.sync import sync_creators_from_snapshot

router = APIRouter()
log = structlog.get_logger()


def _check_creator_crm(shop: Shop) -> None:
    """CREATOR_CRM gate value is 'basic' or 'full' for unlocked tiers."""
    gate_value = get_gate_value(shop, Feature.CREATOR_CRM)
    if gate_value in (False, None, 0):
        from app.core.gates import UPGRADE_MESSAGES

        msg = UPGRADE_MESSAGES.get(Feature.CREATOR_CRM, "Creator CRM cần gói Pro.")
        raise HTTPException(
            status_code=402,
            detail={
                "error": {
                    "code": "FEATURE_LOCKED",
                    "message": msg,
                    "feature": Feature.CREATOR_CRM.value,
                    "upgrade_url": "/settings/billing",
                }
            },
        )


class CreatorProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    shop_id: uuid.UUID
    creator_id: str
    creator_name: str
    gmv_30d: str
    net_revenue_30d: str
    revenue_efficiency_30d: str | None
    avg_refund_rate: str
    total_orders_lifetime: int
    last_order_date: object | None
    total_commission_paid: str
    commission_on_refunded_orders: str
    status: str
    tags: list | None
    negotiated_rate: str | None
    internal_note: str | None
    contact_zalo: str | None
    contact_email: str | None
    performance_label: str
    suggested_max_commission: str | None


def _profile_to_response(p: CreatorProfile) -> CreatorProfileResponse:
    return CreatorProfileResponse(
        id=p.id,
        shop_id=p.shop_id,
        creator_id=p.creator_id,
        creator_name=p.creator_name,
        gmv_30d=str(p.gmv_30d),
        net_revenue_30d=str(p.net_revenue_30d),
        revenue_efficiency_30d=str(p.revenue_efficiency_30d)
        if p.revenue_efficiency_30d is not None
        else None,
        avg_refund_rate=str(p.avg_refund_rate),
        total_orders_lifetime=p.total_orders_lifetime,
        last_order_date=p.last_order_date,
        total_commission_paid=str(p.total_commission_paid),
        commission_on_refunded_orders=str(p.commission_on_refunded_orders),
        status=p.status,
        tags=p.tags,
        negotiated_rate=str(p.negotiated_rate) if p.negotiated_rate is not None else None,
        internal_note=p.internal_note,
        contact_zalo=p.contact_zalo,
        contact_email=p.contact_email,
        performance_label=p.performance_label,
        suggested_max_commission=str(p.suggested_max_commission)
        if p.suggested_max_commission is not None
        else None,
    )


class CreatorProfileUpdateRequest(BaseModel):
    status: str | None = Field(None, pattern="^(active|paused|blacklisted|vip)$")
    tags: list[Annotated[str, Field(max_length=50)]] | None = None
    negotiated_rate: Decimal | None = Field(None, ge=0, le=1)
    internal_note: str | None = Field(None, max_length=1000)
    # Vietnamese mobile: 10–11 digits starting with 0
    contact_zalo: str | None = Field(None, max_length=15, pattern=r"^0\d{9,10}$")
    # Basic email format — same package as notification_email on Shop
    contact_email: str | None = Field(None, max_length=200, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@router.get("/creators")
@limiter.limit("60/minute")
async def list_creators(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["active", "paused", "blacklisted", "vip"] | None = Query(None),
    performance_label: Literal["star", "break_even", "losing"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[CreatorProfileResponse]:
    _check_creator_crm(shop)

    q = select(CreatorProfile).where(CreatorProfile.shop_id == shop.id)
    if status:
        q = q.where(CreatorProfile.status == status)
    if performance_label:
        q = q.where(CreatorProfile.performance_label == performance_label)
    q = q.order_by(CreatorProfile.gmv_30d.desc()).limit(limit)

    rows = await db.scalars(q)
    return [_profile_to_response(r) for r in rows]


@router.get("/creators/{profile_id}")
@limiter.limit("60/minute")
async def get_creator(
    request: Request,
    profile_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreatorProfileResponse:
    _check_creator_crm(shop)

    profile = await db.scalar(
        select(CreatorProfile).where(
            CreatorProfile.id == profile_id,
            CreatorProfile.shop_id == shop.id,
        )
    )
    if not profile:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})
    return _profile_to_response(profile)


@router.patch("/creators/{profile_id}")
@limiter.limit("20/hour")
async def update_creator(
    request: Request,
    profile_id: uuid.UUID,
    body: CreatorProfileUpdateRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreatorProfileResponse:
    _check_creator_crm(shop)

    profile = await db.scalar(
        select(CreatorProfile).where(
            CreatorProfile.id == profile_id,
            CreatorProfile.shop_id == shop.id,
        )
    )
    if not profile:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})

    update_data = body.model_dump(exclude_none=True)

    # Gap #2: When negotiated_rate changes, snapshot the old rate with valid_to=today
    # so 30-day grace period can be applied when computing historical P&L.
    if "negotiated_rate" in update_data and profile.negotiated_rate is not None:
        old_rate = profile.negotiated_rate
        new_rate = Decimal(str(update_data["negotiated_rate"]))
        if old_rate != new_rate:
            today = date.today()
            # Close ALL open snapshots (not just first) to handle any data corruption
            open_snaps_result = await db.scalars(
                select(CommissionSnapshot).where(
                    CommissionSnapshot.shop_id == shop.id,
                    CommissionSnapshot.creator_id == profile.creator_id,
                    CommissionSnapshot.sku_id.is_(None),
                    CommissionSnapshot.valid_to.is_(None),
                )
            )
            for open_snap in open_snaps_result.all():
                open_snap.valid_to = today
            # Create new snapshot for the new rate
            db.add(
                CommissionSnapshot(
                    shop_id=shop.id,
                    creator_id=profile.creator_id,
                    sku_id=None,
                    rate=new_rate,
                    valid_from=today,
                    valid_to=None,
                )
            )

    for field_name, val in update_data.items():
        setattr(profile, field_name, val)

    await db.flush()
    await db.refresh(profile)
    return _profile_to_response(profile)


@router.post("/creators/sync")
@limiter.limit("10/hour")
async def sync_creators(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Upsert creator data from latest InsightSnapshot top_creators_json."""
    _check_creator_crm(shop)

    snapshot = await db.scalar(
        select(InsightSnapshot)
        .where(InsightSnapshot.shop_id == shop.id)
        .order_by(InsightSnapshot.period_end.desc())
        .limit(1)
    )
    if not snapshot:
        raise HTTPException(
            404,
            detail={"error": {"code": "NO_SNAPSHOT", "message": "Chưa có dữ liệu snapshot."}},
        )

    creators_raw: list = snapshot.top_creators_json or []
    if not creators_raw:
        return {"synced": 0, "message": "Không có creator trong snapshot mới nhất."}

    upserted = await sync_creators_from_snapshot(db, shop.id, creators_raw)
    await db.flush()
    log.info("creators.sync", shop_id=str(shop.id), upserted=upserted)
    return {"synced": upserted}


@router.get("/creators/{profile_id}/rate-history")
@limiter.limit("60/hour")
async def get_rate_history(
    request: Request,
    profile_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """
    Gap #2: Return commission rate history for a creator.
    Shows all rate changes with valid_from/valid_to for audit and P&L reconciliation.
    """
    _check_creator_crm(shop)

    profile = await db.scalar(
        select(CreatorProfile).where(
            CreatorProfile.id == profile_id,
            CreatorProfile.shop_id == shop.id,
        )
    )
    if not profile:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND"}})

    snapshots = (
        await db.scalars(
            select(CommissionSnapshot)
            .where(
                CommissionSnapshot.shop_id == shop.id,
                CommissionSnapshot.creator_id == profile.creator_id,
            )
            .order_by(CommissionSnapshot.valid_from.desc())
        )
    ).all()

    return [
        {
            "id": str(s.id),
            "creator_id": s.creator_id,
            "sku_id": s.sku_id,
            "rate": str(s.rate),
            "valid_from": s.valid_from.isoformat(),
            "valid_to": s.valid_to.isoformat() if s.valid_to else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in snapshots
    ]
