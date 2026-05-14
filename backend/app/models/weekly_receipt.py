from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class WeeklyReceipt(Base, TimestampMixin):
    """
    AI-generated weekly money saved receipt.
    INVARIANT: confirmed_saved from Rule Engine only — never AI-calculated.
    """
    __tablename__ = "weekly_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    period_label: Mapped[str] = mapped_column(String(100), nullable=False)

    total_confirmed_saved: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    total_estimated_saved: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    actions_completed_count: Mapped[int] = mapped_column(default=0, nullable=False)

    headline: Mapped[str] = mapped_column(String(300), nullable=False)
    confirmed_section: Mapped[str] = mapped_column(String(1000), nullable=False)
    estimated_section: Mapped[str] = mapped_column(String(1000), nullable=False)
    next_week_focus: Mapped[str] = mapped_column(String(500), nullable=False)
    disclaimer: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # v1.2.0 — Email delivery tracking
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    shop: Mapped[Shop] = relationship(back_populates="weekly_receipts")  # noqa: F821

    __table_args__ = (Index("ix_weekly_receipts_shop_id", "shop_id"),)
