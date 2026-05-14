from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ImportSession(Base, TimestampMixin):
    __tablename__ = "import_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False
    )

    # File info
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # Supabase Storage path
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # FIX BUG-NM5: SHA-256 of file_bytes for duplicate detection per shop
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_type: Mapped[str] = mapped_column(
        String(50), default="unknown", nullable=False
    )  # order_export | transaction_export | settlement_export | unknown
    encoding_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | processing | completed | failed
    can_continue_mode: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # full | limited | blocked

    # Results
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # v2.0.0: platform detected from file headers
    platform: Mapped[str] = mapped_column(
        String(20), default="tiktok", nullable=False, server_default="tiktok"
    )

    # AI rescue message — populated khi Parser detect issues
    ai_rescue_message: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    shop: Mapped[Shop] = relationship(back_populates="import_sessions")  # noqa: F821
    orders: Mapped[list[Order]] = relationship(back_populates="import_session")  # noqa: F821

    __table_args__ = (Index("ix_import_sessions_shop_id_status", "shop_id", "status"),)
