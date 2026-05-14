from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Date, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FeeConfig(Base, TimestampMixin):
    """
    Versioned TikTok Shop fee structure.
    INVARIANT: rates stored as Decimal 0-1 (NOT percentage).
      e.g. 2% platform commission = Decimal("0.02")

    New row khi TikTok thay đổi fee structure — KHÔNG update row cũ.
    InsightSnapshot reference fee_config_version để audit trail.
    """
    __tablename__ = "fee_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # v2.0.0: platform this config applies to
    platform: Mapped[str] = mapped_column(
        String(20), default="tiktok", nullable=False, server_default="tiktok"
    )
    # e.g. "2024-VN-v1", "2025-VN-v2"

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = hiện tại

    # Base rates — Numeric(6,4) vì rates nhỏ, e.g. 0.0200 = 2%
    platform_commission_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    # FIX P1-FeeConfig: transaction_fee 6% từ 09/05/2026
    transaction_fee_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    # FIX P1-FeeConfig: 3,000 VND/completed order từ 27/10/2025
    order_processing_fee_per_order: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    # Per-category overrides: {"mall": "0.1450", "electronics": "0.0150"}
    category_overrides: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Audit
    verified_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (Index("ix_fee_configs_effective_from", "effective_from"),)
