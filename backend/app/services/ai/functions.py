"""
AI Service Functions — 5 behavioral layer functions.
INVARIANT:
- Input = sanitized JSON from Rule Engine
- Output = Pydantic schema validated dict
- Numbers validated by guardrails before returning
- Fallback templates used when validation fails
"""

import structlog

from app.core.config import get_settings
from app.core.redis import ai_narrative_cache_key, cache_get_safe, cache_set_safe
from app.schemas.ai_service import (
    ActionCoachInput,
    ActionCoachOutput,
    AhaNarrativeInput,
    AhaNarrativeOutput,
    ImportRescueInput,
    ImportRescueOutput,
    RefundClusterInput,
    RefundClusterOutput,
    WeeklyReceiptInput,
    WeeklyReceiptOutput,
)
from app.services.ai.client import call_ai
from app.services.ai.guardrails import (
    detect_injection,
    sanitize_for_ai,
    validate_numbers_in_text,
)

settings = get_settings()
log = structlog.get_logger()

DEFAULT_DISCLAIMER = (
    "Số ước tính dựa trên thay đổi metrics so sánh trước/sau action. "
    "Số đã xác nhận là những action seller đánh dấu hoàn thành và có P&L delta thực tế."
)


# ── AI #1: Import Rescue ──────────────────────────────────────────────────────


async def run_import_rescue(
    input_data: ImportRescueInput,
    shop_id: str,
    tier: str = "free",
) -> ImportRescueOutput:
    """
    Detect file format issues and generate user-friendly rescue message.
    Uses small model — low stakes, simple task.
    No cache — every file is different.
    No number validation — no money numbers in output.
    """
    # ADR-AI-001: sanitize_for_ai() calls _sanitize_field() → detect_injection() on all string
    # values and replaces with [SANITIZED]. The separate header loop was redundant and
    # misleading — logging "injection_detected" without actually blocking it at that point.
    sanitized = sanitize_for_ai(input_data.model_dump())

    task = (
        "Phân tích thông tin file upload từ TikTok Shop seller. "
        "Xác định loại file, tìm columns thiếu, hướng dẫn seller nếu cần export lại. "
        "Viết user_message_vi và next_step_instruction bằng tiếng Việt dễ hiểu."
    )

    try:
        result = await call_ai(
            task_prompt=task,
            data_json=sanitized,
            output_schema=ImportRescueOutput,
            shop_id=shop_id,
            function_name="import_rescue",
            use_small_model=True,
            max_tokens=500,
            tier=tier,
        )
        return ImportRescueOutput(**result)
    except Exception as e:
        log.error("ai.import_rescue_failed", error=str(e), shop_id=shop_id)
        # Fallback
        return ImportRescueOutput(
            file_type_guess="unknown",
            file_type_confidence="low",
            missing_columns=input_data.required_columns,
            can_continue_mode="blocked",
            user_message_vi="Tikai chưa nhận ra file này. Vui lòng thử export lại từ TikTok Shop.",
            next_step_instruction="Vào TikTok Shop → Seller Center → Đơn hàng → Xuất file → Chọn 'Order Export'.",
            missing_data=["file_type"],
        )


# ── AI #2: Aha Narrator ───────────────────────────────────────────────────────


async def run_aha_narrator(
    input_data: AhaNarrativeInput,
    shop_id: str,
    snapshot_id: str,
    tier: str = "free",
) -> AhaNarrativeOutput:
    """Cache-backed narrative generation."""
    cache_key = ai_narrative_cache_key(shop_id, snapshot_id, "aha_narrative")

    # Check cache
    cached = await cache_get_safe(cache_key)
    if cached:
        log.info("ai.cache_hit", function="aha_narrator", shop_id=shop_id)
        return AhaNarrativeOutput(**cached)

    sanitized = sanitize_for_ai(input_data.model_dump(mode="json"))
    task = (
        "Viết tóm tắt kết quả kinh doanh tuần này cho seller. "
        "Nêu rõ vấn đề lớn nhất và 1 action cụ thể cần làm hôm nay. "
        "Ngắn gọn, không quá 3 câu cho mỗi field."
    )

    try:
        result = await call_ai(
            task_prompt=task,
            data_json=sanitized,
            output_schema=AhaNarrativeOutput,
            shop_id=shop_id,
            function_name="aha_narrator",
            use_small_model=True,
            max_tokens=400,
            tier=tier,
        )
        output = AhaNarrativeOutput(**result)

        # Validate numbers
        all_text = f"{output.summary} {output.key_insight} {output.top_action_today}"
        validation = validate_numbers_in_text(all_text, input_data.model_dump(mode="json"))
        if not validation.valid:
            log.warning(
                "ai.invented_numbers",
                function="aha_narrator",
                invented=validation.invented_numbers,
                shop_id=shop_id,
            )
            output = _fallback_aha_narrative(input_data)

        # Cache
        await cache_set_safe(
            cache_key, output.model_dump(), settings.ai_narrative_cache_ttl_seconds
        )
        return output

    except Exception as e:
        log.error("ai.aha_narrator_failed", error=str(e), shop_id=shop_id)
        return _fallback_aha_narrative(input_data)


def _fallback_aha_narrative(input_data: AhaNarrativeInput) -> AhaNarrativeOutput:
    leak_count = len(input_data.top_leaks)
    mode_note = (
        " (chưa có giá vốn — đang hiển thị Net Revenue)" if input_data.is_net_revenue_mode else ""
    )
    return AhaNarrativeOutput(
        summary=f"Shop {input_data.shop_name} {input_data.period_label}: GMV {input_data.gmv_total:,.0f}₫, Net Revenue {input_data.net_revenue:,.0f}₫{mode_note}.",
        key_insight=f"Có {leak_count} vấn đề cần xử lý tuần này."
        if leak_count
        else "Chưa phát hiện vấn đề lớn.",
        top_action_today=f"Xem chi tiết {input_data.top_leaks[0].name} nếu có."
        if input_data.top_leaks
        else "Nhập giá vốn để Tikai tính được lợi nhuận chính xác.",
        missing_data=["ai_narrative_unavailable"],
    )


# ── AI #3: Action Coach ───────────────────────────────────────────────────────


async def run_action_coach(
    input_data: ActionCoachInput,
    shop_id: str,
    snapshot_id: str,
    tier: str = "free",
) -> ActionCoachOutput:
    """Generate action recommendation for one ActionTrigger."""
    # FIX BUG-H7: use entity_id (unique) not entity_name[:20] (can collide between shops)
    cache_key = ai_narrative_cache_key(
        shop_id, snapshot_id, f"action_coach_{input_data.rule_id}_{input_data.entity_id}"
    )

    cached = await cache_get_safe(cache_key)
    if cached:
        return ActionCoachOutput(**cached)

    sanitized = sanitize_for_ai(input_data.model_dump(mode="json"))
    task = (
        "Viết 1 action recommendation cụ thể cho seller dựa trên rule trigger này. "
        "recommended_step phải là hành động cụ thể có thể làm trong hôm nay. "
        "Nếu cần cảnh báo rủi ro, ghi vào risk_warning."
    )

    try:
        result = await call_ai(
            task_prompt=task,
            data_json=sanitized,
            output_schema=ActionCoachOutput,
            shop_id=shop_id,
            function_name="action_coach",
            use_small_model=True,
            max_tokens=400,
            tier=tier,
        )
        output = ActionCoachOutput(**result)
        all_text = f"{output.action_title} {output.why_it_matters} {output.recommended_step}"
        validation = validate_numbers_in_text(all_text, input_data.model_dump(mode="json"))
        if not validation.valid:
            log.warning("ai.invented_numbers", function="action_coach", shop_id=shop_id)
            output = _fallback_action_coach(input_data)

        await cache_set_safe(
            cache_key, output.model_dump(), settings.ai_narrative_cache_ttl_seconds
        )
        return output

    except Exception as e:
        log.error("ai.action_coach_failed", error=str(e), shop_id=shop_id)
        return _fallback_action_coach(input_data)


def _fallback_action_coach(input_data: ActionCoachInput) -> ActionCoachOutput:
    return ActionCoachOutput(
        action_title=f"Xem lại {input_data.entity_name}",
        why_it_matters=f"{input_data.metric_label} cần kiểm tra.",
        recommended_step=f"Vào TikTok Shop và kiểm tra {input_data.entity_name} hôm nay.",
        confidence="low",
    )


# ── AI #4: Refund Clusterer ───────────────────────────────────────────────────


async def run_refund_clusterer(
    input_data: RefundClusterInput,
    shop_id: str,
    snapshot_id: str,
    tier: str = "free",
) -> RefundClusterOutput:
    """Cluster refund reasons. Uses standard model (harder text task)."""
    cache_key = ai_narrative_cache_key(shop_id, snapshot_id, "refund_cluster")
    cached = await cache_get_safe(cache_key)
    if cached:
        return RefundClusterOutput(**cached)

    # Check injection in reason texts
    clean_reasons = [r for r in input_data.refund_reasons if not detect_injection(r)]

    sanitized = sanitize_for_ai(
        {
            **input_data.model_dump(mode="json"),
            "refund_reasons": clean_reasons,
        }
    )
    task = (
        "Cluster lý do hoàn hàng thành tối đa 5 nhóm. "
        "Mỗi nhóm có label tiếng Việt, count, pct (0-1), và 2-3 sample reasons. "
        "suggested_actions là danh sách việc cần làm để giảm refund."
    )

    try:
        result = await call_ai(
            task_prompt=task,
            data_json=sanitized,
            output_schema=RefundClusterOutput,
            shop_id=shop_id,
            function_name="refund_clusterer",
            use_small_model=False,  # standard model for clustering
            max_tokens=600,
            tier=tier,
        )
        output = RefundClusterOutput(**result)
        await cache_set_safe(
            cache_key, output.model_dump(), settings.ai_narrative_cache_ttl_seconds
        )
        return output

    except Exception as e:
        log.error("ai.refund_clusterer_failed", error=str(e), shop_id=shop_id)
        return RefundClusterOutput(
            clusters=[],
            suggested_actions=["Kiểm tra lại lý do hoàn hàng thủ công."],
            missing_data=["ai_clustering_unavailable"],
        )


# ── AI #5: Weekly Receipt Writer ─────────────────────────────────────────────


async def run_weekly_receipt(
    input_data: WeeklyReceiptInput,
    shop_id: str,
    tier: str = "free",
) -> WeeklyReceiptOutput:
    """
    Generate weekly money saved receipt.
    No cache — weekly unique.
    MANDATORY: disclaimer cannot be empty.
    """
    sanitized = sanitize_for_ai(input_data.model_dump(mode="json"))
    task = (
        "Viết weekly receipt cho seller. "
        "Phân biệt rõ 'đã xác nhận' (confirmed) vs 'ước tính' (estimated). "
        "disclaimer bắt buộc phải có và giải thích cách tính. "
        "next_week_focus là 1 câu về việc cần làm tuần tới."
    )

    try:
        result = await call_ai(
            task_prompt=task,
            data_json=sanitized,
            output_schema=WeeklyReceiptOutput,
            shop_id=shop_id,
            function_name="weekly_receipt",
            use_small_model=True,
            max_tokens=500,
            tier=tier,
        )
        output = WeeklyReceiptOutput(**result)

        # Validate numbers
        all_text = f"{output.headline} {output.confirmed_section} {output.estimated_section}"
        validation = validate_numbers_in_text(all_text, input_data.model_dump(mode="json"))
        if not validation.valid:
            log.warning("ai.invented_numbers", function="weekly_receipt", shop_id=shop_id)
            output = _fallback_weekly_receipt(input_data)

        # Ensure disclaimer
        if not output.disclaimer.strip():
            output = output.model_copy(update={"disclaimer": DEFAULT_DISCLAIMER})

        return output

    except Exception as e:
        log.error("ai.weekly_receipt_failed", error=str(e), shop_id=shop_id)
        return _fallback_weekly_receipt(input_data)


def _fallback_weekly_receipt(input_data: WeeklyReceiptInput) -> WeeklyReceiptOutput:
    return WeeklyReceiptOutput(
        headline=f"Tuần {input_data.period_label} — {len(input_data.actions_completed)} action hoàn thành",
        confirmed_section=f"Đã xác nhận: {input_data.total_confirmed_saved:,.0f}₫",
        estimated_section=f"Ước tính thêm: ~{input_data.total_estimated_saved:,.0f}₫",
        next_week_focus="Tiếp tục thực hiện các action Tikai gợi ý.",
        disclaimer=DEFAULT_DISCLAIMER,
    )
