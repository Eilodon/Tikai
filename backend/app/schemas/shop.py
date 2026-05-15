import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Valid category slugs — must match industry_data.py Category Literal
_VALID_CATEGORIES = {"fashion", "beauty", "food", "electronics", "home", "baby", "other"}


class CreateShopRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)


class UpdateShopRequest(BaseModel):
    shop_name: str | None = Field(default=None, min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
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
