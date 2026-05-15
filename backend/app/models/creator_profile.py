from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CreatorProfile(Base, TimestampMixin):
    __tablename__ = "creator_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    creator_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Performance (auto-updated from imports)
    gmv_30d: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    net_revenue_30d: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    revenue_efficiency_30d: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    avg_refund_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0")
    )
    total_orders_lifetime: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_commission_paid: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    commission_on_refunded_orders: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    # CRM fields (manual)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    negotiated_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    contact_zalo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Computed (stored)
    performance_label: Mapped[str] = mapped_column(String(20), nullable=False, default="break_even")
    suggested_max_commission: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    __table_args__ = (
        UniqueConstraint("shop_id", "creator_id", name="uq_creator_profiles_shop_creator"),
    )
