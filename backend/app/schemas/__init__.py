from decimal import Decimal
from typing import Literal

# Type aliases — dùng nhất quán trong toàn bộ codebase
MoneyVND = Decimal           # Numeric(20,4), KHÔNG bao giờ float
ConfidenceLevel = Literal["high", "medium", "low"]
ActionStatus = Literal["pending", "done", "dismissed"]
FileType = Literal["order_export", "transaction_export", "settlement_export", "unknown"]
CanContinueMode = Literal["full", "limited", "blocked"]
ActionType = Literal[
    "reduce_voucher", "pause_creator", "fix_pdp", "check_cogs", "review_script"
]
