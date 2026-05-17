from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InsightSnapshot(Base, TimestampMixin):
    """
    Rule Engine output — immutable after creation.
    INVARIANT: tất cả số trong đây đến từ Rule Engine, KHÔNG phải AI.
    AI chỉ đọc snapshot này để generate narratives.
    """

    __tablename__ = "insight_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    import_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Aggregates — Numeric(20, 4)
    gmv_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    total_refunds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refund_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # 0-1
    cash_in_14d: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    # Feature 6: Cash Flow Forecast — additional settlement fields
    cash_in_30d: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    cash_pending_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Rule Engine JSON outputs
    top_leaks_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    top_skus_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    top_creators_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    action_triggers_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Gap #4: orders where platform fees were estimated rather than parsed from CSV
    fee_discrepancy_notes_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Metadata
    rule_engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    fee_config_version: Mapped[str] = mapped_column(String(50), nullable=False)
    cogs_coverage_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0"), nullable=False
    )  # % top-20 SKUs có COGS
    is_net_revenue_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    shop: Mapped[Shop] = relationship(back_populates="insight_snapshots")  # noqa: F821
    ai_actions: Mapped[list[AIAction]] = relationship(back_populates="insight_snapshot")  # noqa: F821

    __table_args__ = (Index("ix_insight_snapshots_shop_id_period", "shop_id", "period_end"),)
