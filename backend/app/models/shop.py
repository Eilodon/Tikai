from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tiktok_shop_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    fee_config_version: Mapped[str] = mapped_column(
        String(50), default="2026-VN-v3", nullable=False
    )
    cogs_map: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # v1.2.0 — Email digest opt-in
    # notification_email: seller's preferred email; falls back to auth email if null
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # P4-2: 14-day Pro trial for new signups
    trial_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # P2-3: Web Push subscription object from browser Push API
    push_subscription_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # v2.1.0: shop category for category-aware refund baselines (industry_data.py slugs)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ZNS prep — Vietnamese phone + ZNS notification toggle
    seller_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zns_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # v2.3.0: Inventory tracking — {sku_id: stock_on_hand (int)}
    stock_map: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)

    # Relationships
    import_sessions: Mapped[list[ImportSession]] = relationship(back_populates="shop")  # noqa: F821
    insight_snapshots: Mapped[list[InsightSnapshot]] = relationship(back_populates="shop")  # noqa: F821
    ai_actions: Mapped[list[AIAction]] = relationship(back_populates="shop")  # noqa: F821
    weekly_receipts: Mapped[list[WeeklyReceipt]] = relationship(back_populates="shop")  # noqa: F821
