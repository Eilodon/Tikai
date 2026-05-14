from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    # INVARIANT: tất cả money fields dùng Numeric(20, 4) — KHÔNG BAOGIỜ Float
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )
    import_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # TikTok identifiers
    tiktok_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_name: Mapped[str] = mapped_column(String(300), nullable=False)
    creator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    creator_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Financial — ALL Numeric(20, 4), default 0 (never null except cogs)
    gmv: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    platform_commission: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    affiliate_commission: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    voucher_cost: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    shipping_subsidy: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False
    )
    # FIX P0-3: TikTok-specific fees missing from original model
    # transaction_fee: 6% of buyer-paid (Phí Giao Dịch) — from 09/05/2026
    transaction_fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False, server_default="0"
    )
    # order_processing_fee: 3,000 VND/order (Phí Xử Lý Đơn Hàng) — from 27/10/2025
    order_processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0"), nullable=False, server_default="0"
    )
    # FIX P0-3: quantity — số lượng sản phẩm/đơn (default 1 nếu export không có cột này)
    # CRITICAL: COGS = cogs_per_unit * quantity, NOT cogs_per_unit * order_count
    quantity: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default="1"
    )
    # cogs: nullable — seller nhập thủ công, có thể chưa có
    cogs: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    # v2.0.0: source platform (default 'tiktok' for backward compat)
    platform: Mapped[str] = mapped_column(
        String(20), default="tiktok", nullable=False, server_default="tiktok"
    )

    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    refund_reason_raw: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    shop: Mapped[Shop] = relationship()  # noqa: F821
    import_session: Mapped[ImportSession] = relationship()  # noqa: F821

    # Indexes for common queries
    __table_args__ = (
        Index("ix_orders_shop_id_order_date", "shop_id", "order_date"),
        Index("ix_orders_shop_id_sku_id", "shop_id", "sku_id"),
        Index("ix_orders_shop_id_creator_id", "shop_id", "creator_id"),
        Index("ix_orders_tiktok_order_id", "tiktok_order_id"),
        Index("ix_orders_shop_id_platform", "shop_id", "platform"),
        Index("ix_orders_shop_id_sku_name", "shop_id", "sku_name"),
    )
