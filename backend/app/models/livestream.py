from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LiveStreamSession(Base):
    __tablename__ = "livestream_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False, index=True)

    # When
    livestream_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    platform_live_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Cost breakdown
    host_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    studio_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    product_sample_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    ads_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    other_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Time window for auto-attribution
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Results (filled after live — can be updated)
    attributed_gmv: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    attributed_orders: Mapped[int] = mapped_column(Integer, default=0)
    attributed_net_revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @hybrid_property
    def total_cost(self) -> Decimal:
        return (
            self.host_cost
            + self.studio_cost
            + self.product_sample_cost
            + self.ads_cost
            + self.other_cost
        )

    @total_cost.expression  # type: ignore[no-redef]
    @classmethod
    def total_cost(cls):
        return (
            cls.host_cost
            + cls.studio_cost
            + cls.product_sample_cost
            + cls.ads_cost
            + cls.other_cost
        )

    @property
    def live_roi(self) -> Decimal | None:
        """True Live ROI = attributed_gmv / total_cost."""
        total = self.total_cost
        if total == 0 or self.attributed_gmv is None:
            return None
        return self.attributed_gmv / total

    @property
    def net_roi(self) -> Decimal | None:
        """Net Live ROI = attributed_net_revenue / total_cost."""
        total = self.total_cost
        if total == 0 or self.attributed_net_revenue is None:
            return None
        return self.attributed_net_revenue / total
