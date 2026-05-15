from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

FileType = Literal["order_export", "transaction_export", "settlement_export", "unknown"]
CanContinueMode = Literal["full", "limited", "blocked"]


@dataclass
class RawOrderRow:
    """
    Normalized output from any parser.
    INVARIANT: ALL money fields are Decimal — NEVER float.

    FIX P0-3: Added quantity (for accurate COGS calculation),
    transaction_fee (TikTok 6% from 09/05/2026),
    and order_processing_fee (3,000 VND/order from 27/10/2025).
    Without these, Net Revenue can be overstated by 6-8%+ per order.
    """

    tiktok_order_id: str
    sku_id: str
    sku_name: str
    gmv: Decimal
    platform_commission: Decimal
    affiliate_commission: Decimal
    voucher_cost: Decimal
    shipping_subsidy: Decimal
    refund_amount: Decimal
    order_date: date
    status: str
    # P0-3: quantity — số lượng sản phẩm trong đơn. Default 1 để backward compat.
    # COGS phải nhân với quantity, không phải order_count.
    quantity: int = 1
    # P0-3: TikTok-specific fees not in base commission
    transaction_fee: Decimal = Decimal("0")  # 6% of buyer-paid from 09/05/2026
    order_processing_fee: Decimal = Decimal("0")  # 3,000 VND/order from 27/10/2025
    creator_id: str | None = None
    creator_name: str | None = None
    refund_reason_raw: str | None = None
    # cogs is None until seller manually inputs
    cogs: Decimal | None = None
    # Shopee-only: parent SKU for variation→parent COGS cascade (Issue 2)
    parent_sku_id: str | None = None


@dataclass
class ParseResult:
    file_type: FileType
    platform: str = "tiktok"  # v2.0.0 — "tiktok" | "shopee" | "unknown"
    rows: list[RawOrderRow] = field(default_factory=list)
    failed_rows: list[dict] = field(default_factory=list)  # original dicts that failed parsing
    missing_columns: list[str] = field(default_factory=list)
    can_continue_mode: CanContinueMode = "full"
    date_range_start: date | None = None
    date_range_end: date | None = None
    encoding_detected: str = "utf-8"
    # Populated by caller for AI rescue input
    sample_rows_masked: list[dict] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
