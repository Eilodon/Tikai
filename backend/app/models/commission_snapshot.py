from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CommissionSnapshot(Base, TimestampMixin):
    """
    Historical commission rate snapshot per creator/SKU.
    Enables the 30-day grace period: when a seller lowers a creator's rate,
    orders in the next 30 days are still attributed to the old agreed rate.
    valid_to=None means this rate is currently active.
    """

    __tablename__ = "commission_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sku_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # NULL = all SKUs
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # 0–1
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = current

    __table_args__ = (
        Index("ix_commission_snapshots_shop_creator", "shop_id", "creator_id"),
        Index("ix_commission_snapshots_valid_from", "shop_id", "creator_id", "valid_from"),
    )
