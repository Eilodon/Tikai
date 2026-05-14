import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateShopRequest(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)


class UpdateShopRequest(BaseModel):
    shop_name: str | None = Field(default=None, min_length=2, max_length=200)
    tiktok_shop_id: str | None = Field(default=None, max_length=100)


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
    created_at: datetime
