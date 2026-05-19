from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_shop, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.gates import Feature, get_gate_value
from app.core.rate_limit import limiter
from app.models.shop import Shop
from app.schemas.shop import CreateShopRequest, ShopResponse, UpdateShopRequest

router = APIRouter()
settings = get_settings()


@router.post("/shops/onboarding", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def create_shop(
    request: Request,
    body: CreateShopRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    """Create shop for authenticated user. One shop per user (tier-enforced)."""
    from sqlalchemy import func

    # Count existing active shops for this user
    shop_count: int = (
        await db.scalar(
            select(func.count())
            .select_from(Shop)
            .where(
                Shop.owner_id == current_user.id,
                Shop.is_active == True,  # noqa: E712
            )
        )
        or 0
    )

    if shop_count > 0:
        # Get any existing shop to check the tier limit (.limit(1) — all user shops share same tier)
        any_shop = await db.scalar(select(Shop).where(Shop.owner_id == current_user.id).limit(1))
        if any_shop:
            max_shops: int = int(get_gate_value(any_shop, Feature.MULTI_SHOP) or 1)
            if shop_count >= max_shops:
                tier = getattr(any_shop, "subscription_tier", "free") or "free"
                if tier == "free":
                    detail_msg = "Gói Free chỉ hỗ trợ 1 shop. Nâng cấp lên Pro (299k/tháng) để thêm tối đa 3 shops."
                elif tier == "pro":
                    detail_msg = "Gói Pro hỗ trợ tối đa 3 shops. Nâng cấp lên Business (799k/tháng) để thêm nhiều hơn."
                else:
                    detail_msg = f"Đã đạt giới hạn {max_shops} shops của gói hiện tại."
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": {
                            "code": "SHOP_LIMIT_REACHED",
                            "message": detail_msg,
                            "upgrade_url": "/settings/billing",
                        }
                    },
                )

    from datetime import datetime, timedelta

    shop = Shop(
        owner_id=current_user.id,
        shop_name=body.shop_name,
        tiktok_shop_id=body.tiktok_shop_id,
        subscription_tier="pro_trial",
        trial_expires_at=datetime.now(UTC) + timedelta(days=14),
    )
    db.add(shop)
    await db.flush()
    await db.refresh(shop)
    return ShopResponse.model_validate(shop)


@router.get("/shops/me")
async def get_shop_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    shop = await db.scalar(
        select(Shop).where(Shop.owner_id == current_user.id, Shop.is_active == True)  # noqa: E712
    )
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SHOP_NOT_FOUND",
                    "message": "Chưa có shop. Vui lòng hoàn thành thiết lập.",
                }
            },
        )
    return ShopResponse.model_validate(shop)


@router.patch("/shops/me")
@limiter.limit("30/hour")
async def update_shop_me(
    request: Request,
    body: UpdateShopRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    shop = await db.scalar(
        select(Shop).where(Shop.owner_id == current_user.id, Shop.is_active == True)  # noqa: E712
    )
    if not shop:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SHOP_NOT_FOUND", "message": "Shop không tồn tại."}},
        )

    if body.shop_name is not None:
        shop.shop_name = body.shop_name
    if body.tiktok_shop_id is not None:
        shop.tiktok_shop_id = body.tiktok_shop_id
    if body.category is not None:
        shop.category = body.category
    if body.seller_phone is not None:
        shop.seller_phone = body.seller_phone
    if body.zns_enabled is not None:
        shop.zns_enabled = body.zns_enabled
    # Gap #5: dynamic settlement window rates
    if body.ldr_rate is not None:
        shop.ldr_rate = body.ldr_rate
    if body.sfcr_rate is not None:
        shop.sfcr_rate = body.sfcr_rate

    await db.flush()
    await db.refresh(shop)
    return ShopResponse.model_validate(shop)


class NotificationSettingsRequest(BaseModel):
    notification_email: str | None = None
    email_digest_enabled: bool | None = None


@router.patch("/shops/me/notifications")
@limiter.limit("10/hour")
async def update_notification_settings(
    request: Request,
    body: NotificationSettingsRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopResponse:
    """Update email notification preferences.
    email_digest_enabled defaults to False until seller opts in.
    notification_email: seller-preferred email (may differ from auth email).
    """
    if body.notification_email is not None:
        if body.notification_email:
            # F-05: use email-validator dep (was only checking "@")
            from email_validator import EmailNotValidError, validate_email

            try:
                validate_email(body.notification_email, check_deliverability=False)
            except EmailNotValidError:
                raise HTTPException(
                    status_code=400,
                    detail={"error": {"code": "INVALID_EMAIL", "message": "Email không hợp lệ."}},
                )
        shop.notification_email = body.notification_email or None
    if body.email_digest_enabled is not None:
        shop.email_digest_enabled = body.email_digest_enabled
    await db.flush()
    return ShopResponse.model_validate(shop)


class _PushSubscriptionKeys(BaseModel):
    auth: str = Field(max_length=256)
    p256dh: str = Field(max_length=512)


class _PushSubscriptionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    endpoint: str = Field(max_length=500)
    expiration_time: int | None = Field(None, alias="expirationTime")
    keys: _PushSubscriptionKeys


class PushSubscriptionRequest(BaseModel):
    subscription: _PushSubscriptionPayload


@router.get("/shops/me/push-vapid-public-key")
async def get_vapid_public_key() -> dict:
    """Return VAPID public key browsers need to subscribe to Web Push. No auth required."""
    return {"public_key": settings.vapid_public_key}


@router.post("/shops/me/push-subscription", status_code=204)
@limiter.limit("20/hour")
async def save_push_subscription(
    request: Request,
    body: PushSubscriptionRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Save browser Web Push subscription for this shop."""
    shop.push_subscription_json = body.subscription.model_dump()
    await db.flush()
