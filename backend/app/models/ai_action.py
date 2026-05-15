from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AIAction(Base, TimestampMixin):
    """
    AI-generated action recommendation.
    INVARIANT:
    - Content fields (title, why, do_today) written by AI, validated before save
    - source_insight_json = snapshot of InsightSnapshot input used (audit trail)
    - actual_impact_json populated AFTER seller completes action + Rule Engine recalculates
    """

    __tablename__ = "ai_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    insight_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("insight_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action classification
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # reduce_voucher | pause_creator | fix_pdp | check_cogs | review_script
    rule_trigger: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # rule_id that generated this

    # AI-written content — validated by guardrails before save
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    why: Mapped[str] = mapped_column(String(500), nullable=False)
    do_today: Mapped[str] = mapped_column(String(500), nullable=False)
    expected_impact: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)  # high | medium | low

    # Audit — snapshot of exact input used for this action
    source_insight_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | done | dismissed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Impact verification — populated 7 days after completion
    actual_impact_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_confirmed_impact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # Relationships
    shop: Mapped[Shop] = relationship(back_populates="ai_actions")  # noqa: F821
    insight_snapshot: Mapped[InsightSnapshot] = relationship(back_populates="ai_actions")  # noqa: F821

    __table_args__ = (Index("ix_ai_actions_shop_id_status", "shop_id", "status"),)
