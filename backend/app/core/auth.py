"""
Auth — Supabase JWT validation.
FIX ISSUE-01: error responses use standard {"error": {...}} format.
"""

import uuid
from datetime import UTC
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.shop import Shop

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)
log = structlog.get_logger()


class AuthenticatedUser:
    def __init__(self, user_id: uuid.UUID, email: str):
        self.id = user_id
        self.email = email


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    """Validate Supabase JWT. Returns AuthenticatedUser or raises 401."""
    if not credentials:
        log.warning("auth.no_credentials")  # L10-M01
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: str | None = payload.get("sub")
        email: str = payload.get("email", "")
        if user_id is None:
            raise ValueError("No sub in token")
        return AuthenticatedUser(user_id=uuid.UUID(user_id), email=email)
    except (JWTError, ValueError) as exc:
        log.warning("auth.jwt_invalid", reason=type(exc).__name__)  # L10-M01
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.",
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_shop(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Shop:
    """INVARIANT: every request that touches business data goes through this."""
    from datetime import datetime

    shop = await db.scalar(
        select(Shop).where(
            Shop.owner_id == current_user.id,
            Shop.is_active == True,  # noqa: E712
        )
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
    # P4-2: auto-expire trial when trial_expires_at is in the past
    if shop.subscription_tier == "pro_trial":
        expires = getattr(shop, "trial_expires_at", None)
        if expires and expires < datetime.now(UTC):
            shop.subscription_tier = "free"
            shop.trial_expires_at = None
            await db.flush()  # S-2: flush only — commit happens when request ends
            await db.refresh(shop)  # L1-M02: reload flushed state to avoid stale reads
    return shop
