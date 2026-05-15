import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Valid category slugs — must match industry_data.py Category Literal
_VALID_CATEGORIES = {"fashion", "beauty", "food", "electronics", "home", "baby", "other"}

_VN_PHONE_RE = re.compile(r"^\d{10,11}$")


class CreateShopRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)


class UpdateShopRequest(BaseModel):
    shop_name: str | None = Field(default=None, min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    seller_phone: str | None = Field(default=None, max_length=20)
    zns_enabled: bool | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
        return v

    @field_validator("seller_phone")
    @classmethod
    def validate_seller_phone(cls, v: str | None) -> str | None:
        if v is not None and not _VN_PHONE_RE.match(v):
            raise ValueError("seller_phone must be 10-11 digits (Vietnamese phone number)")
        return v


class ShopResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    shop_name: str
    tiktok_shop_id: str | None
    subscription_tier: str
    fee_config_version: str
    is_active: bool
    # v1.2.0 email digest fields — may be null if migration not yet run
    notification_email: str | None = None
    email_digest_enabled: bool = False
    # P4-2: trial fields — null for non-trial or expired shops
    trial_expires_at: datetime | None = None
    created_at: datetime
    # v2.1.0: shop category for category-aware leak detection
    category: str | None = None
    # ZNS prep
    seller_phone: str | None = None
    zns_enabled: bool = False
