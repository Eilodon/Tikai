"""
Insights API — get snapshots, history, and trigger recompute.

FIXES:
- BUG-C2: _to_response() now includes top_creators
- BUG-NM1: _safe_parse() prevents 500 on corrupt DB JSON
- NEW: GET /insights/history for week-over-week comparison
- NEW: POST /insights/recompute for instant recalc after COGS update
"""

import csv
import hashlib
import io
import uuid
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.config import get_settings
from app.core.database import get_db
from app.core.gates import Feature, get_history_weeks_limit, require_feature
from app.core.rate_limit import limiter  # v0.5.2: for rate-limiting recompute endpoint
from app.models.fee_config import FeeConfig
from app.models.import_session import ImportSession
from app.models.insight_snapshot import InsightSnapshot
from app.models.order import Order
from app.models.shop import Shop
from app.schemas.insight import (
    ActionTrigger,
    CreatorSummaryItem,
    InsightSnapshotResponse,
    LeakItem,
    SKUSummaryItem,
)
from app.services.benchmarks.industry_data import Category, compare_to_industry
from app.services.rule_engine import FeeConfigData, build_insight
from app.services.rule_engine.baselines import CATEGORY_REFUND_BASELINES

MAX_ORDERS_RECOMPUTE = 50_000  # cap for recompute endpoint to prevent OOM

router = APIRouter()
settings = get_settings()
log = structlog.get_logger()


def _safe_parse(schema_class, items: list) -> list:
    """FIX BUG-NM1: graceful parse — skip corrupt items instead of 500.
    FIX MED-V2-7: log a single summary line if any items failed (not silent).
    """
    if not items:
        return []
    result = []
    error_count = 0
    first_error = None
    for item in items:
        try:
            result.append(schema_class(**item))
        except Exception as e:
            error_count += 1
            if first_error is None:
                first_error = str(e)
    if error_count > 0:
        log.warning(
            "_to_response.parse_errors",
            cls=schema_class.__name__,
            failed=error_count,
            total=len(items),
            first_error=first_error,
        )
    return result


def _to_response(
    snapshot: InsightSnapshot, is_first_import: bool = False
) -> InsightSnapshotResponse:
    days_in_period = 7
    is_partial_period = False
    if snapshot.period_start and snapshot.period_end:
        days_in_period = (snapshot.period_end - snapshot.period_start).days + 1
        is_partial_period = days_in_period < 5

    return InsightSnapshotResponse(
        id=snapshot.id,
        shop_id=snapshot.shop_id,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        gmv_total=snapshot.gmv_total,
        net_revenue=snapshot.net_revenue,
        total_orders=snapshot.total_orders,
        total_refunds=snapshot.total_refunds,
        refund_rate=snapshot.refund_rate,
        cash_in_14d=snapshot.cash_in_14d,
        # Feature 6: Cash Flow Forecast — nullable on old snapshots
        cash_in_30d=getattr(snapshot, "cash_in_30d", None),
        cash_pending_total=getattr(snapshot, "cash_pending_total", None),
        top_leaks=_safe_parse(LeakItem, snapshot.top_leaks_json),
        top_skus=_safe_parse(SKUSummaryItem, snapshot.top_skus_json),
        top_creators=_safe_parse(CreatorSummaryItem, snapshot.top_creators_json),  # FIX BUG-C2
        action_triggers=_safe_parse(ActionTrigger, snapshot.action_triggers_json),
        rule_engine_version=snapshot.rule_engine_version,
        fee_config_version=snapshot.fee_config_version,
        cogs_coverage_pct=snapshot.cogs_coverage_pct,
        is_net_revenue_mode=snapshot.is_net_revenue_mode,
        days_in_period=days_in_period,
        is_partial_period=is_partial_period,
        is_first_import=is_first_import,
        created_at=snapshot.created_at,
    )


@router.get("/insights/latest")
async def get_latest_insight(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InsightSnapshotResponse:
    snapshot = await db.scalar(
        select(InsightSnapshot)
        .where(InsightSnapshot.shop_id == shop.id)
        .order_by(InsightSnapshot.period_end.desc())
        .limit(1)
    )
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Chưa có dữ liệu. Vui lòng import file từ TikTok Shop.",
                }
            },
        )
    total = (
        await db.scalar(
            select(func.count())
            .select_from(InsightSnapshot)
            .where(InsightSnapshot.shop_id == shop.id)
        )
        or 0
    )
    return _to_response(snapshot, is_first_import=(total == 1))


@router.get("/insights/history")
async def get_insight_history(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    weeks: int = Query(4, ge=1, le=52),
) -> list[InsightSnapshotResponse]:
    """Return last N weeks of snapshots (oldest first) for trend comparison."""
    # FIX GAP-M6: cap weeks to tier limit
    max_weeks = get_history_weeks_limit(shop)
    weeks = min(weeks, max_weeks)

    rows = await db.scalars(
        select(InsightSnapshot)
        .where(InsightSnapshot.shop_id == shop.id)
        .order_by(InsightSnapshot.period_end.desc())
        .limit(weeks)
    )
    snapshots = list(rows)
    return [_to_response(s) for s in reversed(snapshots)]


@router.get("/insights/{snapshot_id}")
async def get_insight_by_id(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InsightSnapshotResponse:
    snapshot = await db.scalar(
        select(InsightSnapshot).where(
            InsightSnapshot.id == snapshot_id,
            InsightSnapshot.shop_id == shop.id,  # INVARIANT: shop isolation
        )
    )
    if not snapshot:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy."}}
        )
    return _to_response(snapshot)


@router.get("/insights/{snapshot_id}/benchmark")
async def get_benchmark(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Category = "other",
) -> dict:
    """
    Feature 5: So sánh chỉ số shop với benchmark ngành.
    INVARIANT: mỗi comparison có source field rõ ràng.
    """
    snapshot = await db.scalar(
        select(InsightSnapshot).where(
            InsightSnapshot.id == snapshot_id,
            InsightSnapshot.shop_id == shop.id,
        )
    )
    if not snapshot:
        raise HTTPException(
            404,
            detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy snapshot."}},
        )

    # Compute shop-level margin_pct from top_skus (weighted by GMV)
    top_skus = _safe_parse(SKUSummaryItem, snapshot.top_skus_json or [])
    total_gmv = sum(s.gmv for s in top_skus)
    shop_margin_pct = None
    if total_gmv > 0:
        weighted_margin = sum(s.margin_pct * s.gmv for s in top_skus if s.margin_pct is not None)
        skus_with_margin_gmv = sum(s.gmv for s in top_skus if s.margin_pct is not None)
        if skus_with_margin_gmv > 0:
            shop_margin_pct = weighted_margin / skus_with_margin_gmv

    # Compute fee burden = (gmv - net_revenue) / gmv
    gmv_total = snapshot.gmv_total
    net_revenue = snapshot.net_revenue
    shop_fee_burden_pct = None
    if gmv_total and gmv_total > 0:
        shop_fee_burden_pct = (gmv_total - net_revenue) / gmv_total

    comparisons = compare_to_industry(
        shop_refund_rate=snapshot.refund_rate,
        shop_margin_pct=shop_margin_pct,
        shop_fee_burden_pct=shop_fee_burden_pct,
        category=category,
    )

    return {
        "category": category,
        "comparisons": [c.model_dump() for c in comparisons],
    }


@router.post("/insights/recompute")
@limiter.limit("5/hour")  # FIX v0.5.2: heavy endpoint — load 50k orders + run Rule Engine
async def recompute_insight(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    snapshot_id: uuid.UUID | None = Query(None),
) -> InsightSnapshotResponse:
    """
    Re-run Rule Engine on existing orders with current COGS map.
    Does NOT re-parse file, does NOT re-run AI (uses cached narratives).
    Creates a new InsightSnapshot — instant feedback loop after COGS update.
    """
    # FIX GAP-M6: feature gate
    require_feature(shop, Feature.RE_ANALYSIS)

    # ADR-SEC-004: Python hash() is randomized per process (PYTHONHASHSEED) since 3.3.
    # In multi-process deploys two workers compute different lock_key for the same shop_id
    # → advisory lock does nothing → duplicate snapshots. Use hashlib (always stable).
    from sqlalchemy import text as sa_text

    lock_key = int(hashlib.md5(str(shop.id).encode(), usedforsecurity=False).hexdigest(), 16) % (
        2**31
    )
    locked = await db.scalar(sa_text(f"SELECT pg_try_advisory_xact_lock({lock_key})"))
    if not locked:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "RECOMPUTE_IN_PROGRESS",
                    "message": "Đang có một tính toán khác đang chạy. Vui lòng thử lại sau 5 giây.",
                }
            },
        )

    # 1. Find base snapshot
    query = select(InsightSnapshot).where(InsightSnapshot.shop_id == shop.id)
    if snapshot_id:
        query = query.where(InsightSnapshot.id == snapshot_id)
    else:
        query = query.order_by(InsightSnapshot.created_at.desc()).limit(1)

    base = await db.scalar(query)
    if not base:
        raise HTTPException(
            404, detail={"error": {"code": "NOT_FOUND", "message": "Chưa có snapshot để tính lại."}}
        )

    # 2. Load orders from DB with explicit shop_id filter (defense-in-depth)
    # FIX MED-V2-4: cap at 50,000 orders to prevent OOM (typical week ≤30k orders)
    from app.services.parser.base import RawOrderRow

    order_rows = await db.scalars(
        select(Order)
        .where(
            Order.import_session_id == base.import_session_id,
            Order.shop_id == shop.id,  # defense-in-depth
        )
        .limit(MAX_ORDERS_RECOMPUTE + 1)
    )

    def _to_decimal(val) -> Decimal:
        """FIX MED-V2-5: handle NULL in legacy DB rows (transaction_fee, etc.)"""
        if val is None:
            return Decimal("0")
        if isinstance(val, Decimal):
            return val
        return Decimal(str(val))

    def _order_to_raw_row(o: Order) -> RawOrderRow:
        return RawOrderRow(
            tiktok_order_id=o.tiktok_order_id,
            sku_id=o.sku_id,
            sku_name=o.sku_name,
            gmv=o.gmv,
            platform_commission=o.platform_commission,
            affiliate_commission=o.affiliate_commission,
            voucher_cost=o.voucher_cost,
            shipping_subsidy=o.shipping_subsidy,
            refund_amount=o.refund_amount,
            transaction_fee=_to_decimal(getattr(o, "transaction_fee", None)),
            order_processing_fee=_to_decimal(getattr(o, "order_processing_fee", None)),
            quantity=getattr(o, "quantity", None) or 1,
            order_date=o.order_date,
            status=o.status,
            creator_id=o.creator_id,
            creator_name=o.creator_name,
            refund_reason_raw=o.refund_reason_raw,
        )

    rows = [_order_to_raw_row(o) for o in order_rows]
    if len(rows) > MAX_ORDERS_RECOMPUTE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "TOO_MANY_ORDERS",
                    "message": f"Quá nhiều đơn hàng ({len(rows)}). Tính năng tính lại không hỗ trợ trên {MAX_ORDERS_RECOMPUTE:,} đơn.",
                }
            },
        )
    if not rows:
        raise HTTPException(
            422,
            detail={"error": {"code": "NO_ORDERS", "message": "Không có đơn hàng để tính lại."}},
        )

    # 3. Load fee config — ADR-ARCH-003: use same date-range lookup as process_import.
    # Previously used shop.fee_config_version (wrong: ignores import period, uses current
    # shop config for a historical period → wrong fee rates → wrong P&L).
    # Load platform from the original import session for platform-correct fee lookup.
    # Load ALL configs overlapping [period_start, period_end] so per-order rate
    # selection works correctly when TikTok/Shopee changes fees mid-period.
    import_session = await db.scalar(
        select(ImportSession).where(ImportSession.id == base.import_session_id)
    )
    fee_platform = (import_session.platform if import_session else None) or "tiktok"
    fee_period_end = base.period_end
    fee_period_start = base.period_start

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
                FeeConfig.platform == fee_platform,
                FeeConfig.effective_from <= fee_period_end,
                or_(
                    FeeConfig.effective_to.is_(None),
                    FeeConfig.effective_to >= fee_period_start,
                ),
            )
            .order_by(FeeConfig.effective_from.asc())
        )
    ).all()

    if not fee_configs_db and fee_platform != "tiktok":
        log.warning(
            "recompute_insight.no_platform_fee_config",
            platform=fee_platform,
            snapshot_id=str(base.id),
            shop_id=str(shop.id),
        )
        fee_configs_db = (
            await db.scalars(
                select(FeeConfig)
                .where(
                    FeeConfig.platform == "tiktok",
                    FeeConfig.effective_from <= fee_period_end,
                    or_(
                        FeeConfig.effective_to.is_(None),
                        FeeConfig.effective_to >= fee_period_start,
                    ),
                )
                .order_by(FeeConfig.effective_from.asc())
            )
        ).all()

    if not fee_configs_db:
        raise HTTPException(
            422,
            detail={
                "error": {"code": "FEE_CONFIG_MISSING", "message": "Không tìm thấy cấu hình phí."}
            },
        )

    fee_configs = [_build_fee_config(r) for r in fee_configs_db]

    # 4. Current COGS map — ADR-FIN-004: normalize keys to string+strip to match process_import.py
    raw_cogs = shop.cogs_map or {}
    cogs_map = {str(k).strip(): Decimal(str(v)) for k, v in raw_cogs.items() if v}

    # 5. Re-run Rule Engine
    insight_data = build_insight(
        rows=rows,
        fee_configs=fee_configs,
        cogs_map=cogs_map,
        category_baselines=CATEGORY_REFUND_BASELINES,
        shop_id=str(shop.id),
        rule_engine_version=settings.rule_engine_version,
        top_n_leaks=settings.ai_top_n_leaks,
    )

    # 6. Save new snapshot (recomputed)
    from app.services.rule_engine.settlement_calc import calculate_settlement_forecast

    settlement = calculate_settlement_forecast(rows, reference_date=base.period_end)
    cash_in_14d = settlement.cash_in_14d if settlement.cash_in_14d > 0 else None
    cash_in_30d = settlement.cash_in_30d if settlement.cash_in_30d > 0 else None
    cash_pending_total = settlement.pending_total if settlement.pending_total > 0 else None

    new_snapshot = InsightSnapshot(
        shop_id=shop.id,
        import_session_id=base.import_session_id,
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
    db.add(new_snapshot)
    await db.flush()
    await db.refresh(new_snapshot)
    await db.commit()

    log.info("recompute_insight.done", shop_id=str(shop.id), snapshot_id=str(new_snapshot.id))
    return _to_response(new_snapshot)


# ── CSV Export ────────────────────────────────────────────────────────────────


@router.get("/insights/{snapshot_id}/export.csv")
async def export_snapshot_csv(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Export top SKU P&L from a snapshot as CSV.
    Gated: Feature.CSV_EXPORT (pro/business only).
    """
    require_feature(shop, Feature.CSV_EXPORT)

    snapshot = await db.scalar(
        select(InsightSnapshot).where(
            InsightSnapshot.id == snapshot_id,
            InsightSnapshot.shop_id == shop.id,
        )
    )
    if not snapshot:
        raise HTTPException(
            404,
            detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy snapshot."}},
        )

    top_skus = _safe_parse(SKUSummaryItem, snapshot.top_skus_json or [])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "SKU ID",
            "SKU Name",
            "GMV (VND)",
            "Net Revenue (VND)",
            "Orders",
            "Units Sold",
            "Refund Rate (%)",
            "Margin (VND)",
            "Margin (%)",
            "Health",
            "Affiliate Cost (VND)",
            "Voucher Cost (VND)",
        ]
    )
    for s in top_skus:
        refund_pct = f"{float(s.refund_rate) * 100:.1f}"
        margin_pct = f"{float(s.margin_pct) * 100:.1f}" if s.margin_pct is not None else ""
        writer.writerow(
            [
                s.sku_id,
                s.sku_name,
                str(s.gmv),
                str(s.net_revenue),
                s.order_count,
                s.total_quantity,
                refund_pct,
                str(s.margin) if s.margin is not None else "",
                margin_pct,
                s.health_status,
                str(s.affiliate_commission),
                str(s.voucher_cost),
            ]
        )

    period = f"{snapshot.period_start}_{snapshot.period_end}"
    filename = f"tikai_sku_{period}.csv"
    buf.seek(0)

    log.info(
        "export_snapshot_csv",
        shop_id=str(shop.id),
        snapshot_id=str(snapshot_id),
        rows=len(top_skus),
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
