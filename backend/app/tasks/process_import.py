"""
process_import — ARQ background task.
Runs after file upload: parse → rule engine → AI narratives → save to DB.
INVARIANT: never raises — always updates session status to completed|failed.

FIXES (cumulative through v1.0.0):
- BUG-01: _download_file() now calls storage.download_file()
- BUG-03: eager-loads shop via selectinload to avoid MissingGreenlet
- ISSUE-06: loads cogs_map from shop.cogs_map DB column
- ISSUE-05: integrates settlement_calc for cash_in_14d
- BUG-C1: Order insert now includes transaction_fee, order_processing_fee, quantity
- BUG-NC1: top_creators_json now includes attributed_net_revenue, order_count
- BUG-NC2+H7: ActionCoachInput now passes entity_id for unique cache keys
- BUG-H5: category_baselines replaced with real CATEGORY_REFUND_BASELINES
- BUG-M4: settlement reference_date uses period_end not date.today()
- BUG-NH6: AhaNarrativeInput now includes cash_in_14d
- BUG-NM3: top_n_leaks sourced from settings not hardcoded
- HIGH-V2-2: tier-aware AI call limit (not global Free limit for all)
- v1.0.0: FeeConfigData now includes transaction_fee_rate + order_processing_fee_per_order
- v1.0.0: get_ai_calls_limit imported at module level (was lazy import inside function body)
- v2.0.1 FIX: Order insert now includes platform=parse_result.platform
  IMPACT: Without this, all Shopee orders were stored with platform="tiktok" (server_default),
  breaking per-platform P&L queries and the ix_orders_shop_id_platform index.
"""

import asyncio
import uuid
from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.storage import download_file as storage_download
from app.models.ai_action import AIAction
from app.models.fee_config import FeeConfig
from app.models.import_session import ImportSession
from app.models.insight_snapshot import InsightSnapshot
from app.models.order import Order
from app.schemas.ai_service import ActionCoachInput, AhaNarrativeInput, ImportRescueInput
from app.schemas.insight import LeakItem
from app.services.ai import run_action_coach, run_aha_narrator, run_import_rescue
from app.services.parser import parse_order_csv
from app.services.rule_engine import FeeConfigData, build_insight
from app.services.rule_engine.baselines import CATEGORY_REFUND_BASELINES
from app.services.rule_engine.settlement_calc import calculate_settlement_forecast

settings = get_settings()
log = structlog.get_logger()


async def process_import(ctx: dict, session_id: str) -> None:
    AsyncSessionLocal: async_sessionmaker = ctx["db_session_factory"]  # noqa: N806

    async with AsyncSessionLocal() as db:
        session = await db.scalar(
            select(ImportSession)
            .where(ImportSession.id == uuid.UUID(session_id))
            .options(selectinload(ImportSession.shop))
        )
        if not session:
            log.error("process_import.session_not_found", session_id=session_id)
            return

        try:
            session.status = "processing"
            await db.flush()
            # ADR-ARCH-002: commit status=processing BEFORE heavy work.
            # If ARQ SIGKILL's this job at job_timeout=300s, a flush-only transaction
            # is rolled back → status stays "pending" → cleanup_stuck_imports never
            # catches it → seller's session stuck forever in "pending".
            # After this commit, cleanup_stuck_imports correctly finds it as "processing".
            await db.commit()

            # 1. Download from Supabase Storage
            file_bytes = await storage_download(session.file_path)

            # 2. Parse
            parse_result = parse_order_csv(file_bytes, session.original_filename)
            session.file_type = parse_result.file_type
            session.encoding_detected = parse_result.encoding_detected
            session.date_range_start = parse_result.date_range_start
            session.date_range_end = parse_result.date_range_end
            session.rows_failed = len(parse_result.failed_rows)
            session.can_continue_mode = parse_result.can_continue_mode

            # Compute tier early — needed for per-tier AI budget checks on all AI calls below
            _tier = getattr(session.shop, "subscription_tier", "free") or "free"

            # 3. AI import rescue
            rescue_input = ImportRescueInput(
                headers=parse_result.headers,
                sample_rows=parse_result.sample_rows_masked,
                file_size_kb=session.file_size_bytes // 1024,
                required_columns=[
                    "tiktok_order_id",
                    "gmv",
                    "order_date",
                    "platform_commission",
                    "affiliate_commission",
                ],
            )
            rescue_output = await run_import_rescue(rescue_input, str(session.shop_id), tier=_tier)
            session.ai_rescue_message = rescue_output.model_dump()

            if parse_result.can_continue_mode == "blocked":
                session.status = "failed"
                session.error_summary = {
                    "reason": "blocked",
                    "missing": parse_result.missing_columns,
                }
                await db.flush()
                await db.commit()
                return

            # 4. Save orders (bulk)
            # v2.0.1 FIX: platform MUST be set explicitly on each Order row.
            # migration 0005 added orders.platform with server_default="tiktok",
            # so Shopee orders were silently stored as "tiktok" without this field.
            # That broke ix_orders_shop_id_platform and all per-platform P&L queries.
            _order_platform = parse_result.platform  # "tiktok" | "shopee" | "unknown"
            orders_to_insert = [
                Order(
                    shop_id=session.shop_id,
                    import_session_id=session.id,
                    tiktok_order_id=row.tiktok_order_id,
                    sku_id=row.sku_id,
                    sku_name=row.sku_name,
                    creator_id=row.creator_id,
                    creator_name=row.creator_name,
                    gmv=row.gmv,
                    platform_commission=row.platform_commission,
                    affiliate_commission=row.affiliate_commission,
                    voucher_cost=row.voucher_cost,
                    shipping_subsidy=row.shipping_subsidy,
                    refund_amount=row.refund_amount,
                    transaction_fee=row.transaction_fee,
                    order_processing_fee=row.order_processing_fee,
                    quantity=row.quantity,
                    order_date=row.order_date,
                    status=row.status,
                    refund_reason_raw=row.refund_reason_raw,
                    platform=_order_platform,  # FIX v2.0.1: was missing → all Shopee = "tiktok"
                )
                for row in parse_result.rows
            ]
            db.add_all(orders_to_insert)
            session.rows_parsed = len(orders_to_insert)
            # v2.0.0: track platform on import_session (for import history badge)
            if hasattr(session, "platform"):
                session.platform = _order_platform
            await db.flush()

            # 5. Load FeeConfig — per-order lookup across the full import period.
            # Load ALL configs that overlap [period_start, period_end] so orders placed
            # before a mid-period rate change use the correct (older) rates.
            shop = session.shop
            platform = parse_result.platform
            import_period_end = parse_result.date_range_end or date.today()
            import_period_start = parse_result.date_range_start or import_period_end

            def _build_fee_config(db_row) -> FeeConfigData:
                return FeeConfigData(
                    version=db_row.version,
                    platform_commission_rate=db_row.platform_commission_rate,
                    transaction_fee_rate=db_row.transaction_fee_rate,
                    order_processing_fee_per_order=db_row.order_processing_fee_per_order,
                    category_overrides={
                        k: Decimal(str(v)) for k, v in (db_row.category_overrides or {}).items()
                    },
                    effective_from=db_row.effective_from,
                    effective_to=db_row.effective_to,
                )

            fee_configs_db = (
                await db.scalars(
                    select(FeeConfig)
                    .where(
                        FeeConfig.platform == platform,
                        FeeConfig.effective_from <= import_period_end,
                        or_(
                            FeeConfig.effective_to.is_(None),
                            FeeConfig.effective_to >= import_period_start,
                        ),
                    )
                    .order_by(FeeConfig.effective_from.asc())
                )
            ).all()

            if not fee_configs_db and platform != "tiktok":
                log.warning(
                    "process_import.no_platform_fee_config",
                    platform=platform,
                    session_id=session_id,
                )
                fee_configs_db = (
                    await db.scalars(
                        select(FeeConfig)
                        .where(
                            FeeConfig.platform == "tiktok",
                            FeeConfig.effective_from <= import_period_end,
                            or_(
                                FeeConfig.effective_to.is_(None),
                                FeeConfig.effective_to >= import_period_start,
                            ),
                        )
                        .order_by(FeeConfig.effective_from.asc())
                    )
                ).all()

            if not fee_configs_db:
                log.error(
                    "process_import.fee_config_missing",
                    session_id=session_id,
                    fee_config_version=shop.fee_config_version,
                )
                session.status = "completed_with_caveats"
                session.error_summary = {
                    "warning": "fee_config_missing",
                    "user_message_vi": (
                        "Không tìm thấy cấu hình phí phù hợp. "
                        "Kết quả P&L có thể không chính xác. "
                        "Vui lòng liên hệ hỗ trợ."
                    ),
                    "fee_config_version": shop.fee_config_version,
                }
                await db.flush()
                await db.commit()
                return

            fee_configs = [_build_fee_config(r) for r in fee_configs_db]
            if len(fee_configs) > 1:
                log.info(
                    "process_import.multi_fee_config",
                    count=len(fee_configs),
                    versions=[c.version for c in fee_configs],
                    session_id=session_id,
                )

            # 6. Load COGS map
            # ADR-FIN-004: normalize keys — frontend may send int keys or trailing spaces,
            # causing a silent key miss → COGS never applied → margin stays None.
            raw_cogs = shop.cogs_map or {}
            cogs_map: dict[str, Decimal] = {
                str(sku_id).strip(): Decimal(str(val)) for sku_id, val in raw_cogs.items() if val
            }

            # 7. Run Rule Engine
            insight_data = build_insight(
                rows=parse_result.rows,
                fee_configs=fee_configs,
                cogs_map=cogs_map,
                category_baselines=CATEGORY_REFUND_BASELINES,
                shop_id=str(session.shop_id),
                rule_engine_version=settings.rule_engine_version,
                top_n_leaks=settings.ai_top_n_leaks,
                shop_category=getattr(shop, "category", None),
            )

            settlement = calculate_settlement_forecast(
                parse_result.rows,
                reference_date=parse_result.date_range_end,
            )
            cash_in_14d = settlement.cash_in_14d if settlement.cash_in_14d > 0 else None
            cash_in_30d = settlement.cash_in_30d if settlement.cash_in_30d > 0 else None
            cash_pending_total = settlement.pending_total if settlement.pending_total > 0 else None

            # 9. Save InsightSnapshot
            snapshot = InsightSnapshot(
                shop_id=session.shop_id,
                import_session_id=session.id,
                period_start=insight_data.period_start,
                period_end=insight_data.period_end,
                gmv_total=insight_data.gmv_total,
                net_revenue=insight_data.net_revenue,
                total_orders=insight_data.total_orders,
                total_refunds=insight_data.total_refunds,
                refund_rate=insight_data.refund_rate,
                cash_in_14d=cash_in_14d,
                cash_in_30d=cash_in_30d,
                cash_pending_total=cash_pending_total,
                top_leaks_json=[
                    {
                        "type": leak.type,
                        "id": leak.id,
                        "name": leak.name,
                        "estimated_loss": str(leak.estimated_loss),
                        "reason": leak.reason,
                        "confidence": leak.confidence,
                        "can_act_now": leak.can_act_now,
                    }
                    for leak in insight_data.top_leaks
                ],
                top_skus_json=[
                    {
                        "sku_id": s.sku_id,
                        "sku_name": s.sku_name,
                        "gmv": str(s.gmv),
                        "net_revenue": str(s.net_revenue),
                        "order_count": s.order_count,
                        "total_quantity": s.total_quantity,
                        "refund_rate": str(s.refund_rate),
                        "margin_pct": str(s.margin_pct) if s.margin_pct is not None else None,
                        "margin": str(s.margin) if s.margin is not None else None,
                        "gmv_rank": s.gmv_rank,
                        "affiliate_commission": str(s.affiliate_commission),
                        "voucher_cost": str(s.voucher_cost),
                        "health_status": s.health_status,
                        "health_reasons": s.health_reasons,
                    }
                    for s in insight_data.top_skus
                ],
                top_creators_json=[
                    {
                        "creator_id": c.creator_id,
                        "creator_name": c.creator_name,
                        "attributed_gmv": str(c.attributed_gmv),
                        "attributed_net_revenue": str(c.attributed_net_revenue),
                        "total_commission": str(c.total_commission),
                        "order_count": c.order_count,
                        "revenue_efficiency": str(c.revenue_efficiency)
                        if c.revenue_efficiency is not None
                        else None,
                        "performance_label": c.performance_label,
                        "suggested_max_commission_rate": str(c.suggested_max_commission_rate)
                        if c.suggested_max_commission_rate is not None
                        else None,
                        "commission_on_refunded_orders": str(c.commission_on_refunded_orders),
                    }
                    for c in insight_data.top_creators
                ],
                action_triggers_json=[
                    {
                        "rule_id": t.rule_id,
                        "entity_type": t.entity_type,
                        "entity_id": t.entity_id,
                        "entity_name": t.entity_name,
                        "metric_key": t.metric_key,
                        "metric_value": str(t.metric_value),
                        "priority": t.priority,
                    }
                    for t in insight_data.action_triggers
                ],
                rule_engine_version=insight_data.rule_engine_version,
                fee_config_version=insight_data.fee_config_version,
                cogs_coverage_pct=insight_data.cogs_coverage_pct,
                is_net_revenue_mode=insight_data.is_net_revenue_mode,
            )
            db.add(snapshot)
            await db.flush()
            await db.refresh(snapshot)

            # Auto-sync creator profiles — fire and forget (must NEVER fail the import)
            try:
                from app.services.creators.sync import sync_creators_from_snapshot

                synced = await sync_creators_from_snapshot(
                    db, session.shop_id, snapshot.top_creators_json or []
                )
                await db.flush()
                log.info(
                    "process_import.creators_synced", shop_id=str(session.shop_id), synced=synced
                )
            except Exception as e:
                log.warning("process_import.creator_sync_failed", error=str(e))

            # 10. Run Aha Narrator
            period_label = (
                f"tuần từ {insight_data.period_start.strftime('%d/%m')} "
                f"đến {insight_data.period_end.strftime('%d/%m')}"
            )
            aha_input = AhaNarrativeInput(
                shop_name=shop.shop_name,
                period_label=period_label,
                gmv_total=insight_data.gmv_total,
                net_revenue=insight_data.net_revenue,
                cash_in_14d=cash_in_14d,
                top_leaks=[LeakItem(**lk) for lk in snapshot.top_leaks_json],
                is_net_revenue_mode=insight_data.is_net_revenue_mode,
                cogs_coverage_pct=insight_data.cogs_coverage_pct,
            )
            # Aha Narrator is non-critical — a failure must not abort the import.
            try:
                await run_aha_narrator(
                    aha_input, str(session.shop_id), str(snapshot.id), tier=_tier
                )
            except Exception as aha_err:
                log.warning(
                    "process_import.aha_narrator_failed", session_id=session_id, error=str(aha_err)
                )

            # F-1B-06: explicit tier-based AI call limits (replaces opaque * 5 multiplier)
            # _tier already computed above (near step 3) for budget checks
            _tier_limits = {
                "free": settings.ai_max_calls_per_import_free,
                "pro": settings.ai_max_calls_per_import_pro,
                "pro_trial": settings.ai_max_calls_per_import_pro,  # trial gets pro limit
                "business": settings.ai_max_calls_per_import_business,
            }
            ai_limit = _tier_limits.get(_tier, settings.ai_max_calls_per_import_free)
            # 11. Run Action Coach — parallel calls via asyncio.gather() for latency
            triggers = insight_data.action_triggers[:ai_limit]

            async def _run_single_coach(trigger) -> AIAction | None:
                try:
                    action_input = ActionCoachInput(
                        rule_id=trigger.rule_id,
                        entity_id=trigger.entity_id,
                        entity_name=trigger.entity_name,
                        metric_key=trigger.metric_key,
                        metric_value=trigger.metric_value,
                        metric_label=_metric_label(trigger.metric_key),
                        context_json={
                            "rule_id": trigger.rule_id,
                            "entity_type": trigger.entity_type,
                            "priority": trigger.priority,
                        },
                    )
                    action_output = await run_action_coach(
                        action_input, str(session.shop_id), str(snapshot.id), tier=_tier
                    )
                    return AIAction(
                        shop_id=session.shop_id,
                        insight_snapshot_id=snapshot.id,
                        action_type=_rule_to_action_type(trigger.rule_id),
                        rule_trigger=trigger.rule_id,
                        title=action_output.action_title,
                        why=action_output.why_it_matters,
                        do_today=action_output.recommended_step,
                        expected_impact=action_output.risk_warning or "Cải thiện margin",
                        confidence=action_output.confidence,
                        source_insight_json={
                            "trigger": trigger.rule_id,
                            "entity": trigger.entity_id,
                            "metric_key": trigger.metric_key,
                            "metric_value": str(trigger.metric_value),
                        },
                    )
                except Exception as coach_err:
                    log.warning(
                        "process_import.action_coach_failed",
                        session_id=session_id,
                        rule_id=trigger.rule_id,
                        error=str(coach_err),
                    )
                    return None

            coach_results = await asyncio.gather(*[_run_single_coach(t) for t in triggers])
            for ai_action in coach_results:
                if ai_action is not None:
                    db.add(ai_action)

            await db.flush()
            # P0-1 fix: store top 5 SKUs for post-import COGS prompt
            session.top_skus_for_cogs = [
                {"sku_id": s.sku_id, "sku_name": s.sku_name, "gmv": str(s.gmv)}
                for s in insight_data.top_skus[:5]
            ]
            session.status = "completed"
            await db.flush()
            await db.commit()

            log.info(
                "process_import.completed",
                session_id=session_id,
                rows_parsed=session.rows_parsed,
                leaks=len(insight_data.top_leaks),
                actions=len(triggers),
                cash_in_14d=str(cash_in_14d) if cash_in_14d else None,
            )

        except Exception as e:
            log.exception("process_import.failed", session_id=session_id, error=str(e))
            user_message_vi = _map_exception_to_user_message(e)
            try:
                session.status = "failed"
                session.error_summary = {
                    "error_type": type(e).__name__,
                    "user_message_vi": user_message_vi,
                    "internal_detail": str(e)[:200],
                }
                await db.flush()
                await db.commit()
            except Exception as flush_err:
                log.error("process_import.flush_failed", error=str(flush_err))
            # Best-effort: clean up the uploaded file from storage when import fails.
            # Avoids accumulation of orphan files from repeatedly-failing imports.
            # Non-fatal: failure to clean up is logged but never re-raises.
            if session.file_path:
                try:
                    from app.core.storage import delete_file as storage_delete_file

                    await storage_delete_file(session.file_path)
                    log.info(
                        "process_import.storage_cleaned_on_failure",
                        session_id=session_id,
                        file_path=session.file_path,
                    )
                except Exception as cleanup_err:
                    log.warning(
                        "process_import.storage_cleanup_failed",
                        session_id=session_id,
                        error=str(cleanup_err),
                    )


def _map_exception_to_user_message(exc: Exception) -> str:
    """Map known exception types to Vietnamese user messages. Never leak internals."""
    import pandas as pd

    from app.services.parser.exceptions import UnsupportedFileTypeError

    if isinstance(exc, UnsupportedFileTypeError):
        return "File không phải định dạng TikTok Shop hợp lệ. Vui lòng dùng file export từ Seller Center."
    if isinstance(exc, pd.errors.ParserError):
        return "File bị lỗi hoặc không thể đọc. Vui lòng thử export lại từ TikTok Seller Center."
    if isinstance(exc, UnicodeDecodeError):
        return "File có encoding không hợp lệ. Vui lòng lưu lại dưới định dạng UTF-8 và thử lại."
    if isinstance(exc, ValueError) and "budget" in str(exc).lower():
        return (
            "Hệ thống AI đã đạt giới hạn sử dụng tháng này. Kết quả phân tích cơ bản vẫn khả dụng."
        )
    if isinstance(exc, MemoryError):
        return "File quá lớn để xử lý. Vui lòng chia nhỏ file (tối đa 30,000 đơn) và thử lại."
    return "Đã xảy ra lỗi trong quá trình xử lý file. Vui lòng thử lại hoặc liên hệ hỗ trợ."


_METRIC_LABELS: dict[str, str] = {
    "margin": "Biên lợi nhuận",
    "margin_pct": "Tỷ lệ lợi nhuận",
    "refund_rate": "Tỷ lệ hoàn hàng",
    "revenue_efficiency": "Hiệu quả doanh thu (creator)",
    "cogs": "Giá vốn",
}


def _metric_label(metric_key: str) -> str:
    return _METRIC_LABELS.get(metric_key, metric_key.replace("_", " ").title())


def _rule_to_action_type(rule_id: str) -> str:
    return {
        "sku_margin_negative": "reduce_voucher",
        "creator_roi_below_one": "pause_creator",
        "sku_refund_spike": "fix_pdp",
        "cogs_missing_top_sku": "check_cogs",
    }.get(rule_id, "check_cogs")
