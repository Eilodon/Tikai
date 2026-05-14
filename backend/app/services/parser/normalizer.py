"""
Parser normalizer — column mapping, money parsing, date parsing, PII masking.
v2.0.0: Added SHOPEE_COLUMN_ALIASES + platform-aware build_column_map().
"""
import copy
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

# ── TikTok column aliases ──────────────────────────────────────────────────────
COLUMN_ALIASES: dict[str, list[str]] = {
    "tiktok_order_id": [
        "Order ID", "Order No.", "Mã đơn hàng", "order id",
    ],
    "sku_id": [
        "SKU ID", "Product ID", "Seller SKU", "Mã SKU",
    ],
    "sku_name": [
        "Product Name", "Item Name", "SKU Name", "Tên sản phẩm", "Tên SKU",
    ],
    "gmv": [
        "Original Price", "Buyer Paid", "GMV",
        "Paid Price", "Giá thanh toán", "Số tiền người mua trả",
    ],
    "platform_commission": [
        "Platform Commission Fee", "Commission Fee", "Phí hoa hồng nền tảng",
        "TikTok Commission", "Phí hoa hồng TikTok",
    ],
    "affiliate_commission": [
        "Affiliate Commission", "Creator Commission", "Affiliate Partner Commission",
        "Hoa hồng affiliate", "Hoa hồng creator",
    ],
    "voucher_cost": [
        "Seller Discount", "Seller Voucher", "Seller Promo",
        "Voucher từ người bán", "Giảm giá từ người bán",
    ],
    "shipping_subsidy": [
        "Shipping Fee Subsidy", "Shipping Subsidy", "Phí vận chuyển hỗ trợ",
        "Seller Shipping Fee",
    ],
    "refund_amount": [
        "Refund Amount", "Returned Amount", "Refund", "Số tiền hoàn",
        "Số tiền hoàn trả",
    ],
    "order_date": [
        "Order Creation Time", "Order Date", "Created Time",
        "Ngày tạo đơn", "Thời gian tạo đơn",
    ],
    "status": [
        "Order Status", "Status", "Trạng thái đơn", "Trạng thái",
    ],
    "creator_id": [
        "Affiliate Partner ID", "Creator ID", "Affiliate ID",
        "Mã affiliate", "Mã creator",
    ],
    "creator_name": [
        "Affiliate Partner", "Creator Name", "Affiliate Name",
        "Tên affiliate", "Tên creator",
    ],
    "refund_reason_raw": [
        "Return Reason", "Refund Reason", "Return/Refund Reason",
        "Lý do hoàn", "Lý do trả hàng",
    ],
    "quantity": [
        "Quantity", "Product Quantity", "Qty", "Số lượng", "SL",
    ],
    "transaction_fee": [
        "Transaction Fee", "Platform Transaction Fee",
        "Phí giao dịch", "Phí giao dịch nền tảng",
    ],
    "order_processing_fee": [
        "Order Processing Fee", "Processing Fee",
        "Phí xử lý đơn hàng", "Phí xử lý",
    ],
}

# ── Shopee VN column aliases ──────────────────────────────────────────────────
# Source: Shopee Seller Center VN → Order Management → Export Order
# Verified against real Shopee VN exports (May 2026)
SHOPEE_COLUMN_ALIASES: dict[str, list[str]] = {
    "tiktok_order_id": [    # reuse canonical name — represents any platform's order ID
        "Order ID", "Mã đơn hàng", "order id",
    ],
    "sku_id": [
        "Product SKU ID", "Parent SKU Reference No.", "Variation SKU",
        "Mã SKU", "Mã biến thể", "SKU Reference No.",
    ],
    "sku_name": [
        "Product Name", "Tên sản phẩm",
        "Variation Name", "Product Variation",
    ],
    "gmv": [
        "Original Price", "Product Price", "Unit Price",
        "Giá sản phẩm", "Selling Price", "Buyer Paid Price",
        "Giá bán", "Tổng tiền hàng",
    ],
    "platform_commission": [
        "Commission Fee", "Seller Commission",
        "Phí hoa hồng",
    ],
    "affiliate_commission": [
        "Affiliate Commission Fee", "Shopee Affiliate Commission",
        "Phí affiliate", "Commission from Shopee Affiliate",
    ],
    "voucher_cost": [
        "Seller Voucher", "Seller Discount", "Seller Absorbed Coin Cashback",
        "Voucher từ shop", "Giảm giá từ shop",
    ],
    "shipping_subsidy": [
        "Shipping Fee Subsidy", "Shipping Rebate Seller",
        "Phí vận chuyển hỗ trợ bởi shop",
    ],
    "refund_amount": [
        "Return Amount", "Refund Amount",
        "Số tiền hoàn", "Tiền hoàn lại",
    ],
    "order_date": [
        "Order Creation Date", "Order Paid Time",
        "Ngày đặt hàng", "Thời gian đặt hàng",
    ],
    "status": [
        "Order Status", "Trạng thái đơn hàng",
    ],
    "quantity": [
        "Quantity", "Amount",
        "Số lượng",
    ],
    # Shopee bundles transaction fee differently — maps to same canonical
    "transaction_fee": [
        "Transaction Fee",
    ],
    # Shopee does NOT have a per-order processing fee — leave empty
    # (apply_fee_config will NOT estimate it for Shopee since the fee config has 0)
    "order_processing_fee": [],
    # Shopee affiliate handled differently — creator_id usually absent
    "creator_id": [],
    "creator_name": [
        "Affiliate Partner", "KOL Name",
    ],
    "refund_reason_raw": [
        "Return/Refund Reason", "Lý do hoàn hàng",
    ],
}

# ── Date formats ──────────────────────────────────────────────────────────────
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
]

# PII fields to mask before sending to AI
PII_FIELDS = {
    "buyer_name", "customer_name", "buyer_username",
    "recipient_name", "receiver_name",
    "buyer_address", "shipping_address", "address",
    "buyer_phone", "phone", "phone_number",
    "buyer_email", "email",
}

MONEY_STRIP_PATTERN = re.compile(r"[₫đVND,\s]", re.IGNORECASE)


def build_column_map(headers: list[str], platform: str = "tiktok") -> dict[str, str]:
    """
    Map actual CSV/Excel headers → canonical field names.
    v2.0.0: platform-aware — uses SHOPEE_COLUMN_ALIASES when platform == "shopee".

    Returns {canonical_name: actual_header} for matched columns.
    Unknown/unmatched columns are silently ignored (parser uses defaults).
    """
    alias_source = SHOPEE_COLUMN_ALIASES if platform == "shopee" else COLUMN_ALIASES
    headers_lower = {h.lower().strip(): h for h in headers}
    result: dict[str, str] = {}

    for canonical, aliases in alias_source.items():
        for alias in aliases:
            if alias.lower() in headers_lower:
                result[canonical] = headers_lower[alias.lower()]
                break

    return result


def parse_money(raw: Any) -> Decimal:
    """
    INVARIANT: always returns Decimal. NEVER float.
    Input examples: "₫186,000", "186000.00", "186,000 VND", 186000, None, NaN,
                    "(186,000)" (accounting notation for negative)
    F-1B-07: handle parenthetical negatives e.g. Shopee accounting format.
    """
    if raw is None:
        return Decimal("0")
    if isinstance(raw, float):
        if raw != raw:  # NaN check
            return Decimal("0")
        return Decimal(str(raw))
    if isinstance(raw, (int, Decimal)):
        return Decimal(str(raw))

    cleaned = MONEY_STRIP_PATTERN.sub("", str(raw)).strip()
    if not cleaned or cleaned in ("-", "N/A", "n/a", ""):
        return Decimal("0")
    # F-1B-07: handle accounting notation (186000) → -186000
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def parse_date(raw: Any) -> date | None:
    """Parse date string in various TikTok/Shopee formats."""
    if raw is None or str(raw).strip() == "":
        return None
    from datetime import datetime
    raw_str = str(raw).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw_str, fmt).date()
        except ValueError:
            continue
    return None


def mask_pii(row: dict) -> dict:
    """
    Mask PII fields for AI input.
    Returns new dict — does NOT mutate original.
    """
    masked = copy.deepcopy(row)
    for key in list(masked.keys()):
        if key.lower().replace(" ", "_") in PII_FIELDS:
            masked[key] = "***"
        elif isinstance(masked[key], str) and re.match(r"^\d{10,11}$", masked[key].strip()):
            masked[key] = "***"
    return masked
