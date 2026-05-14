"""
File type detector — identifies TikTok and Shopee export formats from column headers.
v2.0.0: Added Shopee fingerprints; detect_file_type() now returns platform as 3rd element.
"""

# ── TikTok column fingerprints ────────────────────────────────────────────────
COLUMN_FINGERPRINTS: dict[str, list[str]] = {
    "order_export": [
        "order id", "product name", "sku id",
        "original price", "order status", "order creation time",
    ],
    "transaction_export": [
        "transaction id", "transaction type",
        "settlement amount", "transaction date",
    ],
    "settlement_export": [
        "payout id", "payout amount",
        "order id", "payout time",
    ],
    # v2.0.0: Shopee fingerprints (EN headers)
    "shopee_order_export": [
        "order id", "product name", "product sku id",
        "original price", "order status", "order creation date",
        "transaction fee",
    ],
    # v2.0.0: Shopee VN export (Vietnamese headers)
    "shopee_order_export_vi": [
        "mã đơn hàng", "tên sản phẩm", "mã sku",
        "giá sản phẩm", "trạng thái đơn hàng", "ngày đặt hàng",
    ],
}

# ── Vietnamese column aliases for fingerprinting ──────────────────────────────
COLUMN_FINGERPRINTS_VI: dict[str, list[str]] = {
    "order_export": [
        "mã đơn hàng", "tên sản phẩm", "mã sku",
        "giá gốc", "trạng thái đơn", "ngày tạo đơn",
    ],
    "transaction_export": [
        "mã giao dịch", "loại giao dịch",
        "số tiền quyết toán", "ngày giao dịch",
    ],
    "settlement_export": [
        "mã thanh toán", "số tiền thanh toán",
        "mã đơn hàng", "thời gian thanh toán",
    ],
    # Shopee EN export with VI UI labels — shares base columns with _vi variant
    "shopee_order_export": [
        "mã đơn hàng", "tên sản phẩm", "mã sku",
        "giá sản phẩm", "trạng thái đơn hàng", "ngày đặt hàng",
    ],
    # Shopee VN export — uses Shopee-VN-specific column names not present in EN variant
    "shopee_order_export_vi": [
        "mã đơn hàng", "tên sản phẩm", "mã sku sản phẩm",
        "giá bán", "trạng thái đơn hàng", "ngày đặt hàng",
        "phí hoa hồng",
    ],
}

# v2.0.0: Map file_type → platform
PLATFORM_MAP: dict[str, str] = {
    "order_export":          "tiktok",
    "transaction_export":    "tiktok",
    "settlement_export":     "tiktok",
    "shopee_order_export":   "shopee",
    "shopee_order_export_vi": "shopee",
    "unknown":               "unknown",
}

CONFIDENCE_HIGH = 0.7
CONFIDENCE_MEDIUM = 0.4


def detect_file_type(headers: list[str]) -> tuple[str, float, str]:
    """
    Identify file type and platform from column headers.

    v2.0.0: Returns (file_type, confidence_score, platform).
    - file_type: "order_export" | "shopee_order_export" | "shopee_order_export_vi" | ...
    - confidence_score: 0.0–1.0
    - platform: "tiktok" | "shopee" | "unknown"

    Scoring: max(EN_match_fraction, VI_match_fraction) per fingerprint set.
    Disambiguation: if two file types score the same (e.g. Shopee EN vs TikTok
    when "order id" and "original price" appear in both), the one with more
    unique fingerprint matches wins.

    BACKWARD COMPAT: callers using the 2-tuple (file_type, score) still work via
    tuple unpacking — Python lets you do `ftype, score = detect_file_type(h)` only
    if they unpack exactly 2 values, which would fail. Callers updated in v2.0.0.
    Callers needing only 2 values should use: `ftype, score, _ = detect_file_type(h)`.
    """
    normalized = {h.lower().strip() for h in headers}
    scores: dict[str, float] = {}

    for ftype, required_en in COLUMN_FINGERPRINTS.items():
        required_vi = COLUMN_FINGERPRINTS_VI.get(ftype, [])
        en_match = sum(1 for col in required_en if col in normalized) / max(len(required_en), 1)
        vi_match = (
            sum(1 for col in required_vi if col in normalized) / len(required_vi)
            if required_vi else 0.0
        )
        scores[ftype] = max(en_match, vi_match)

    best_type = max(scores, key=lambda k: scores[k])
    best_score = scores[best_type]

    if best_score < CONFIDENCE_MEDIUM:
        return "unknown", best_score, "unknown"

    platform = PLATFORM_MAP.get(best_type, "unknown")
    return best_type, best_score, platform


def confidence_label(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return "high"
    if score >= CONFIDENCE_MEDIUM:
        return "medium"
    return "low"
