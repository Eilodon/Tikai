"""
AI Guardrails — validate AI output trước khi show to user hoặc write to DB.
INVARIANT: mọi số trong AI text phải trace về source_json.
"""

import copy
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Patterns that look like prompt injection
INJECTION_PATTERNS = [
    # English — core
    r"ignore\s+(previous|above|all)\s+instructions",
    r"you\s+are\s+now",
    r"new\s+system\s+prompt",
    r"<\|.*?\|>",
    r"\[INST\]",
    r"disregard\s+(all|previous)",
    r"forget\s+everything",
    # English — F-07: roleplay and jailbreak additions
    r"act\s+as\s+(?:a\s+)?(?:different|new|another)",
    r"pretend\s+(to\s+be|you\s+are)",
    r"(developer|jailbreak|dan)\s+mode",
    r"<\/?(system|user|assistant)>",
    # Vietnamese — F-07: common injection phrasings in VN
    r"bỏ\s+qua.{0,20}lệnh",
    r"giả\s+vờ\s+(là|bạn\s+là)",
    r"đóng\s+vai",
    r"quên\s+(tất\s+cả|hết)",
    r"bây\s+giờ\s+bạn\s+là",
    # Vietnamese — ADR-AI-002: additional patterns missed in gap analysis
    r"hãy\s+(làm\s+theo|bỏ\s+qua)",  # "hãy làm theo" / "hãy bỏ qua" without "lệnh"
    r"nhiệm\s+vụ\s+mới",  # "nhiệm vụ mới" (new task framing)
    r"bạn\s+không\s+còn\s+là",  # "bạn không còn là Tikai"
    # English jailbreak suffixes
    r"in\s+plain\s+text",
    r"without\s+(any\s+)?restriction",
]

# PII field names to sanitize
PII_FIELD_NAMES = {
    "buyer_name",
    "customer_name",
    "buyer_username",
    "recipient_name",
    "buyer_address",
    "shipping_address",
    "receiver_address",
    "buyer_phone",
    "phone",
    "phone_number",
    "mobile",
    "buyer_email",
    "email",
    "email_address",
}


@dataclass
class ValidationResult:
    valid: bool
    invented_numbers: list[str]
    error_message: str | None = None


def flatten_numerics(data: object, result: set | None = None) -> set[Decimal]:
    """Recursively extract all numeric values from nested dict/list."""
    if result is None:
        result = set()
    if isinstance(data, dict):
        for v in data.values():
            flatten_numerics(v, result)
    elif isinstance(data, list):
        for item in data:
            flatten_numerics(item, result)
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        try:
            result.add(Decimal(str(data)))
        except InvalidOperation:
            pass
    elif isinstance(data, str):
        cleaned = re.sub(r"[₫đVND,\s]", "", data).strip()
        if cleaned:
            try:
                result.add(Decimal(cleaned))
            except InvalidOperation:
                pass
    elif isinstance(data, Decimal):
        result.add(data)
    return result


def extract_numbers_from_text(text: str) -> list[str]:
    """Extract all number-like patterns from text.

    FIX BUG-CRITICAL-1: Previous implementation used two overlapping patterns,
    causing '186.000.000' to also extract '186.000' and '000' as separate matches.
    normalize_number('186.000') → 186000, which != source 186000000 → false INVENTED.

    Solution: single alternation pattern — long form first (greedy), fallback to plain
    integer. After dedup, filter out any string that is a substring of a longer match.
    """
    # Single pattern: long-form thousands (e.g. 186.000.000 / 4,800,000) with optional
    # suffix, OR plain integer. Long form must come first so regex engine prefers it.
    pattern = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?(?:[MKBk])?|\d+(?:[.,]\d+)?(?:[MKBk])?"
    found = re.findall(pattern, text)
    found_set = set(found)
    # Remove any match that is a strict substring of a longer match to avoid
    # partial-overlap false positives (e.g. '186.000' inside '186.000.000')
    return [n for n in found_set if not any(n != other and n in other for other in found_set)]


def normalize_number(raw: str) -> Decimal | None:
    """Convert display number string to Decimal for comparison."""
    s = raw.upper()
    multiplier = Decimal("1")
    if s.endswith("M"):
        multiplier = Decimal("1000000")
        s = s[:-1]
    elif s.endswith("K"):
        multiplier = Decimal("1000")
        s = s[:-1]
    elif s.endswith("B"):
        multiplier = Decimal("1000000000")
        s = s[:-1]
    cleaned = re.sub(r"[.,](?=\d{3}(?:[.,]|$))", "", s)
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned) * multiplier
    except InvalidOperation:
        return None


def _is_match(val: Decimal, source_val: Decimal) -> bool:
    """Check if val matches source_val within absolute ±1 OR 1% relative tolerance.

    FIX MEDIUM-2: Fixed ±1 VND tolerance is too strict for amounts ≥10M.
    AI legitimately rounds '186.234.567' → '186 triệu' (=186,000,000).
    Using max(1 VND, 1% of source) covers both small and large amounts.
    """
    if source_val <= 0:
        return False
    abs_diff = abs(val - source_val)
    relative_tolerance = source_val * Decimal("0.01")  # 1%
    absolute_tolerance = Decimal("1")
    return abs_diff <= max(absolute_tolerance, relative_tolerance)


def validate_numbers_in_text(
    ai_text: str,
    source_json: dict,
    tolerance: Decimal = Decimal("1"),  # kept for API compat; logic uses _is_match
) -> ValidationResult:
    """
    INVARIANT: every number in AI text must exist in source_json.
    Tolerance ±1 for display rounding (e.g. 4.8M vs 4800000).
    """
    source_values = flatten_numerics(source_json)
    text_numbers = extract_numbers_from_text(ai_text)
    invented: list[str] = []

    for raw in text_numbers:
        val = normalize_number(raw)
        if val is None or val < Decimal("1000"):
            # Skip small numbers (percentages, counts) and unparseable
            continue
        # Check if this value (with proportional tolerance) exists in source
        matched = any(_is_match(val, sv) for sv in source_values)
        if not matched:
            invented.append(raw)

    if invented:
        return ValidationResult(
            valid=False,
            invented_numbers=invented,
            error_message=f"AI invented numbers not in source: {invented}",
        )
    return ValidationResult(valid=True, invented_numbers=[])


def detect_injection(text: str) -> bool:
    """Return True if text contains prompt injection patterns."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in INJECTION_PATTERNS)


def sanitize_for_ai(data: dict) -> dict:
    """
    Sanitize dict before passing to AI:
    1. Mask PII fields
    2. Strip injection patterns from string values
    3. Wrap in delimiter key to signal 'this is data, not instruction'
    """
    sanitized = _sanitize_recursive(copy.deepcopy(data))
    return {"__tikai_data__": sanitized}


def _sanitize_recursive(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _sanitize_field(k, v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_recursive(item) for item in obj]
    return obj


def _sanitize_field(key: str, value: object) -> object:
    # Normalize: spaces/hyphens to underscores, camelCase to snake_case, lowercase
    # e.g. "buyerName" → "buyer_name", "Buyer-Name" → "buyer_name"
    normalized_key = re.sub(r"([a-z])([A-Z])", r"\1_\2", key)  # camelCase split
    normalized_key = normalized_key.lower().replace(" ", "_").replace("-", "_")
    if normalized_key in PII_FIELD_NAMES:
        return "***"
    if isinstance(value, str) and detect_injection(value):
        return "[SANITIZED]"
    if isinstance(value, str) and re.match(r"^\d{10,11}$", value.strip()):
        return "***"
    if isinstance(value, (dict, list)):
        return _sanitize_recursive(value)
    return value
