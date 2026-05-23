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
from typing import Annotated, Any

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
from app.services.benchmarks.industry_data import LAST_UPDATED, Category, compare_to_industry
from app.services.rule_engine import FeeConfigData, build_insight
from app.services.rule_engine.baselines import CATEGORY_REFUND_BASELINES
from app.services.rule_engine.creator_cohort import analyze_creator_cohort
from app.services.rule_engine.price_recommender import recommend_price

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
            result.append(schema_class.model_validate(item))
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
        # Gap #4: fee estimation discrepancy notes — empty list for old snapshots
        fee_discrepancy_notes=getattr(snapshot, "fee_discrepancy_notes_json", []) or [],
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
    # L5-M01: reject requests that exceed the tier limit (was silently capping)
    max_weeks = get_history_weeks_limit(shop)
    if weeks > max_weeks:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "WEEKS_EXCEEDS_TIER_LIMIT",
                    "message": f"Gói hiện tại chỉ hỗ trợ tối đa {max_weeks} tuần lịch sử. Nâng cấp tại /settings/billing.",
                    "max_weeks": max_weeks,
                    "upgrade_url": "/settings/billing",
                }
            },
        )

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
    Response includes data_age_days so callers can display data freshness.
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
    shop_margin_pct: Decimal | None = None
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

    from app.core.redis import cache_get_safe

    # Apply Redis overrides for benchmark values before comparison
    async def _redis_override(metric: str, default: Decimal) -> Decimal:
        key = f"tikai:benchmark:{category}:{metric}"
        cached = await cache_get_safe(key)
        if cached and "value" in cached:
            try:
                return Decimal(str(cached["value"]))
            except Exception:
                pass
        return default

    from app.services.benchmarks.industry_data import (
        AVG_FEE_BURDEN,
        MARGIN_BENCHMARKS,
        REFUND_RATE_BENCHMARKS,
    )

    # Load potentially overridden benchmark values
    bench_refund = await _redis_override("refund_rate", REFUND_RATE_BENCHMARKS[category])
    bench_margin = await _redis_override("margin_pct", MARGIN_BENCHMARKS[category])
    bench_fee = await _redis_override("fee_burden_pct", AVG_FEE_BURDEN[category])

    # L12-M01: pass overrides as kwargs instead of monkey-patching module globals,
    # which caused a race condition under concurrent requests.
    comparisons = compare_to_industry(
        shop_refund_rate=snapshot.refund_rate,
        shop_margin_pct=shop_margin_pct,
        shop_fee_burden_pct=shop_fee_burden_pct,
        category=category,
        refund_benchmark_override=bench_refund,
        margin_benchmark_override=bench_margin,
        fee_benchmark_override=bench_fee,
    )

    from datetime import date

    data_age_days = (date.today() - LAST_UPDATED).days
    return {
        "category": category,
        "comparisons": [c.model_dump() for c in comparisons],
        "data_age_days": data_age_days,
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
    locked = await db.scalar(sa_text("SELECT pg_try_advisory_xact_lock(:k)").bindparams(k=lock_key))
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
        shop_category=getattr(shop, "category", None),
    )

    # 6. Save new snapshot (recomputed)
    from app.services.rule_engine.settlement_calc import calculate_settlement_forecast

    settlement = calculate_settlement_forecast(
        rows,
        reference_date=base.period_end,
        ldr_rate=getattr(shop, "ldr_rate", None),
        sfcr_rate=getattr(shop, "sfcr_rate", None),
    )
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
        # Gap #4: persist fee estimation discrepancy notes
        fee_discrepancy_notes_json=insight_data.fee_discrepancy_notes,
    )
    db.add(new_snapshot)
    await db.flush()
    await db.refresh(new_snapshot)
    await db.commit()

    log.info("recompute_insight.done", shop_id=str(shop.id), snapshot_id=str(new_snapshot.id))
    return _to_response(new_snapshot)


# ── Price Floor Dashboard ─────────────────────────────────────────────────────


@router.get("/insights/{snapshot_id}/price-floors")
async def get_price_floors(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Feature: Price Floor Dashboard — "giá sàn" per SKU.

    For each top SKU, computes:
    - price_floor_at_0_margin: minimum selling price to break even
    - price_floor_at_10_margin: minimum to reach 10% margin
    - buffer_vnd: gap between avg selling price and break-even floor
    - risk_level: "high" if buffer < 15% of floor, "medium" < 30%, "low" otherwise

    Only SKUs with COGS data can compute meaningful floors. SKUs without COGS
    return risk_level="unknown".
    """
    require_feature(shop, Feature.BENCHMARKS)

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

    # Load current fee config for rate data
    fee_config_row = await db.scalar(
        select(FeeConfig)
        .where(FeeConfig.platform == "tiktok")
        .order_by(FeeConfig.effective_from.desc())
        .limit(1)
    )

    platform_commission_rate = (
        fee_config_row.platform_commission_rate if fee_config_row else Decimal("0.125")
    )
    transaction_fee_rate = (
        fee_config_row.transaction_fee_rate if fee_config_row else Decimal("0.06")
    )
    order_processing_fee = (
        fee_config_row.order_processing_fee_per_order if fee_config_row else Decimal("3000")
    )

    raw_cogs = shop.cogs_map or {}
    cogs_map = {str(k).strip(): Decimal(str(v)) for k, v in raw_cogs.items() if v}

    top_skus = _safe_parse(SKUSummaryItem, snapshot.top_skus_json or [])

    results = []
    for sku in top_skus:
        cogs_per_unit = cogs_map.get(sku.sku_id)

        # Estimate per-SKU rates from aggregated data
        sku_gmv = sku.gmv if sku.gmv > 0 else Decimal("1")
        affiliate_rate = sku.affiliate_commission / sku_gmv
        voucher_rate = sku.voucher_cost / sku_gmv

        # Average selling price (GMV / units sold)
        units = sku.total_quantity if sku.total_quantity > 0 else sku.order_count or 1
        avg_selling_price = sku_gmv / Decimal(units)

        if cogs_per_unit is None:
            results.append(
                {
                    "sku_id": sku.sku_id,
                    "sku_name": sku.sku_name,
                    "avg_selling_price": str(avg_selling_price.quantize(Decimal("1"))),
                    "price_floor_at_0_margin": None,
                    "price_floor_at_10_margin": None,
                    "current_margin_pct": str(sku.margin_pct)
                    if sku.margin_pct is not None
                    else None,
                    "buffer_vnd": None,
                    "risk_level": "unknown",
                }
            )
            continue

        try:
            rec_0 = recommend_price(
                cogs_per_unit=cogs_per_unit,
                target_margin_pct=Decimal("0"),
                platform_commission_rate=platform_commission_rate,
                transaction_fee_rate=transaction_fee_rate,
                order_processing_fee=order_processing_fee,
                affiliate_rate=affiliate_rate,
                voucher_rate=voucher_rate,
            )
            floor_0 = rec_0.min_price
        except ValueError:
            floor_0 = None

        try:
            rec_10 = recommend_price(
                cogs_per_unit=cogs_per_unit,
                target_margin_pct=Decimal("0.10"),
                platform_commission_rate=platform_commission_rate,
                transaction_fee_rate=transaction_fee_rate,
                order_processing_fee=order_processing_fee,
                affiliate_rate=affiliate_rate,
                voucher_rate=voucher_rate,
            )
            floor_10 = rec_10.min_price
        except ValueError:
            floor_10 = None

        buffer_vnd = (avg_selling_price - floor_0).quantize(Decimal("1")) if floor_0 else None
        if buffer_vnd is None or floor_0 is None:
            risk_level = "unknown"
        elif buffer_vnd < 0:
            risk_level = "critical"
        elif floor_0 > 0 and buffer_vnd / floor_0 < Decimal("0.15"):
            risk_level = "high"
        elif floor_0 > 0 and buffer_vnd / floor_0 < Decimal("0.30"):
            risk_level = "medium"
        else:
            risk_level = "low"

        results.append(
            {
                "sku_id": sku.sku_id,
                "sku_name": sku.sku_name,
                "avg_selling_price": str(avg_selling_price.quantize(Decimal("1"))),
                "price_floor_at_0_margin": str(floor_0) if floor_0 is not None else None,
                "price_floor_at_10_margin": str(floor_10) if floor_10 is not None else None,
                "current_margin_pct": str(sku.margin_pct) if sku.margin_pct is not None else None,
                "buffer_vnd": str(buffer_vnd) if buffer_vnd is not None else None,
                "risk_level": risk_level,
            }
        )

    return {
        "snapshot_id": str(snapshot_id),
        "fee_config_version": snapshot.fee_config_version,
        "skus": results,
    }


# ── CSV Export ────────────────────────────────────────────────────────────────


def _safe_csv_cell(value: object) -> str:
    """Sanitize a cell value to prevent CSV formula injection.

    Spreadsheet applications (Excel, Google Sheets) evaluate cells starting
    with '=', '+', '-', '@', '\\t', or '\\r' as formulas, enabling data
    exfiltration via crafted SKU names (e.g. '=HYPERLINK(...)').
    Prefix with a single quote to force string interpretation.
    """
    s = str(value) if value is not None else ""
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + s
    return s


@router.get("/insights/{snapshot_id}/export.csv")
async def export_snapshot_csv(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query("standard", pattern="^(standard|misa)$"),
) -> StreamingResponse:
    """Export top SKU P&L from a snapshot as CSV.
    Gated: Feature.CSV_EXPORT (pro/business only).
    format=misa: Xuất theo chuẩn Misa (tên cột tiếng Việt, định dạng kế toán).
    """
    require_feature(shop, Feature.CSV_EXPORT)
    if format == "misa":
        require_feature(shop, Feature.MISA_EXPORT)

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
    period = f"{snapshot.period_start}_{snapshot.period_end}"

    buf = io.StringIO()
    writer = csv.writer(buf)

    if format == "misa":
        # Misa-compatible format: Vietnamese headers, accountant-friendly columns
        # Misa expects: Mã chứng từ, Ngày, Diễn giải, TK Nợ, TK Có, Số tiền
        # For SKU P&L we map to a simplified Misa revenue/cost structure
        writer.writerow(
            [
                "Mã SKU",
                "Tên sản phẩm",
                "Kỳ báo cáo",
                "Doanh thu gộp (đ)",
                "Doanh thu thuần (đ)",
                "Số lượng bán",
                "Số đơn hàng",
                "Tỷ lệ hoàn (%)",
                "Giá vốn (đ)",
                "Lợi nhuận gộp (đ)",
                "Tỷ suất lợi nhuận (%)",
                "Chi phí affiliate (đ)",
                "Chi phí voucher (đ)",
                "Trạng thái",
            ]
        )
        for s in top_skus:
            refund_pct = f"{s.refund_rate * 100:.1f}"
            margin_pct = f"{s.margin_pct * 100:.1f}" if s.margin_pct is not None else "N/A"
            writer.writerow(
                [
                    _safe_csv_cell(s.sku_id),
                    _safe_csv_cell(s.sku_name),
                    period.replace("_", " đến "),
                    str(s.gmv),
                    str(s.net_revenue),
                    s.total_quantity,
                    s.order_count,
                    refund_pct,
                    # BUG-C2 FIX: SKUSummaryItem has no total_cogs field → AttributeError.
                    # Use margin (net_revenue - COGS) which is already computed and serialized.
                    str(s.margin) if s.margin is not None else "Chưa nhập",
                    str(s.margin) if s.margin is not None else "N/A",
                    margin_pct,
                    str(s.affiliate_commission),
                    str(s.voucher_cost),
                    _safe_csv_cell(s.health_status),
                ]
            )
        filename = f"tikai_misa_{period}.csv"
    else:
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
            refund_pct = f"{s.refund_rate * 100:.1f}"
            margin_pct = f"{s.margin_pct * 100:.1f}" if s.margin_pct is not None else ""
            writer.writerow(
                [
                    _safe_csv_cell(s.sku_id),
                    _safe_csv_cell(s.sku_name),
                    str(s.gmv),
                    str(s.net_revenue),
                    s.order_count,
                    s.total_quantity,
                    refund_pct,
                    str(s.margin) if s.margin is not None else "",
                    margin_pct,
                    _safe_csv_cell(s.health_status),
                    str(s.affiliate_commission),
                    str(s.voucher_cost),
                ]
            )
        filename = f"tikai_sku_{period}.csv"

    buf.seek(0)

    log.info(
        "export_snapshot_csv",
        shop_id=str(shop.id),
        snapshot_id=str(snapshot_id),
        rows=len(top_skus),
        format=format,
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Creator Cohort Report ─────────────────────────────────────────────────────


@router.get("/insights/creator-cohort")
@limiter.limit("20/hour")
async def get_creator_cohort(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period_ids: str = Query(..., description="Comma-separated snapshot UUIDs (max 8)"),
) -> list[dict]:
    """Compare creator performance across multiple snapshot periods."""
    require_feature(shop, Feature.CREATOR_CRM)  # L8-H01: gate enforced
    raw_ids = [p.strip() for p in period_ids.split(",") if p.strip()]
    if not raw_ids:
        raise HTTPException(422, detail={"error": {"code": "MISSING_PERIOD_IDS"}})
    if len(raw_ids) > 8:
        raise HTTPException(422, detail={"error": {"code": "TOO_MANY_PERIODS", "max": 8}})

    parsed_ids: list[uuid.UUID] = []
    for raw in raw_ids:
        try:
            parsed_ids.append(uuid.UUID(raw))
        except ValueError:
            raise HTTPException(422, detail={"error": {"code": "INVALID_UUID", "value": raw}})

    snapshots = await db.scalars(
        select(InsightSnapshot).where(
            InsightSnapshot.id.in_(parsed_ids),
            InsightSnapshot.shop_id == shop.id,  # IDOR guard
        )
    )
    snapshot_list = list(snapshots)

    # Verify all requested IDs belong to this shop — L1-M01: no UUID list in error (enumeration risk)
    found_ids = {s.id for s in snapshot_list}
    if any(i not in found_ids for i in parsed_ids):
        raise HTTPException(
            404,
            detail={
                "error": {"code": "PERIODS_NOT_FOUND", "message": "One or more periods not found."}
            },
        )

    # Build period-keyed summaries from stored JSON
    # Use period_end as the period label key
    creator_summaries_by_period: dict[str, list] = {}
    for snapshot in sorted(snapshot_list, key=lambda s: s.period_end):
        period_key = str(snapshot.period_end)
        creators = _safe_parse(CreatorSummaryItem, snapshot.top_creators_json or [])
        creator_summaries_by_period[period_key] = creators

    insights_list = analyze_creator_cohort(creator_summaries_by_period)

    return [
        {
            "creator_id": i.creator_id,
            "creator_name": i.creator_name,
            "trend": i.trend,
            "gmv_first_period": str(i.gmv_first_period),
            "gmv_last_period": str(i.gmv_last_period),
            "change_pct": str(i.change_pct),
            "periods_active": i.periods_active,
            "avg_orders_per_period": str(i.avg_orders_per_period),
        }
        for i in insights_list
    ]


# ── CM3 Endpoint ──────────────────────────────────────────────────────────────


@router.get("/insights/{snapshot_id}/cm3")
async def get_cm3(
    snapshot_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Compute CM3 = CM2 - direct ads cost - product sample cost for livestream sessions in period."""
    from app.models.livestream import LiveStreamSession
    from app.services.rule_engine.pl_calculator import compute_cm3

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

    # Load livestream sessions within the snapshot period
    from sqlalchemy import and_

    sessions = await db.scalars(
        select(LiveStreamSession).where(
            and_(
                LiveStreamSession.shop_id == shop.id,
                LiveStreamSession.livestream_date >= snapshot.period_start,
                LiveStreamSession.livestream_date <= snapshot.period_end,
            )
        )
    )
    session_list = list(sessions)

    livestream_costs = [
        {
            "ads_cost": s.ads_cost,
            "product_sample_cost": s.product_sample_cost,
        }
        for s in session_list
    ]

    cm3, cm3_pct = compute_cm3(
        cm2=snapshot.net_revenue,
        gmv=snapshot.gmv_total,
        livestream_costs=livestream_costs,
    )

    total_direct = sum(
        Decimal(str(lc["ads_cost"])) + Decimal(str(lc["product_sample_cost"]))
        for lc in livestream_costs
    )

    return {
        "cm3": str(cm3),
        "cm3_margin_pct": str(cm3_pct) if cm3_pct is not None else None,
        "livestream_total_cost": str(total_direct),
        "livestream_session_count": len(session_list),
        "note_vi": (
            "CM3 chưa tính phí quảng cáo TikTok Ads (chỉ tính chi phí host/studio/mẫu trong kỳ)"
        ),
    }


# ── MCN / Multi-shop Aggregate ────────────────────────────────────────────────


@router.get("/insights/aggregate")
@limiter.limit(
    "10/minute"
)  # BUG-M2 FIX: MCN query fans out to all shops — rate-limit to prevent DoS
async def get_aggregate_overview(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    v2.3.0: Cross-shop aggregate P&L for the owner's Business/Enterprise account.
    Returns total GMV, net revenue, refund rate and a per-shop breakdown
    based on each shop's latest snapshot. Business+ tier required.

    Intended for MCN operators and multi-brand sellers managing ≥2 shops.
    """
    require_feature(shop, Feature.MCN_AGGREGATE)

    # All shops owned by the same account
    owner_shops = await db.scalars(
        select(Shop).where(Shop.owner_id == shop.owner_id, Shop.is_active.is_(True))
    )
    shop_list = list(owner_shops)

    if not shop_list:
        return {"shops": [], "aggregate": {}}

    # BUG-M2 FIX: old subquery joined on created_at == max(created_at), which returns
    # duplicate rows when two snapshots share an exact timestamp (NTP hiccup, concurrent
    # imports). Use DISTINCT ON with (created_at DESC, id DESC) tie-breaking instead —
    # PostgreSQL guarantees exactly one row per shop_id.
    snap_rows = await db.scalars(
        select(InsightSnapshot)
        .where(InsightSnapshot.shop_id.in_([s.id for s in shop_list]))
        .order_by(
            InsightSnapshot.shop_id,
            InsightSnapshot.created_at.desc(),
            InsightSnapshot.id.desc(),
        )
        .distinct(InsightSnapshot.shop_id)
    )
    snapshots = {s.shop_id: s for s in snap_rows}

    total_gmv = Decimal("0")
    total_net_revenue = Decimal("0")
    total_orders = 0
    total_refunds = 0
    per_shop: list[dict[str, Any]] = []

    for s in shop_list:
        snap = snapshots.get(s.id)
        if snap is None:
            per_shop.append(
                {
                    "shop_id": str(s.id),
                    "shop_name": s.shop_name,
                    "has_data": False,
                }
            )
            continue

        shop_gmv = snap.gmv_total or Decimal("0")
        shop_nr = snap.net_revenue or Decimal("0")
        shop_orders = snap.total_orders or 0
        shop_refunds = snap.total_refunds or 0

        total_gmv += shop_gmv
        total_net_revenue += shop_nr
        total_orders += shop_orders
        total_refunds += shop_refunds

        per_shop.append(
            {
                "shop_id": str(s.id),
                "shop_name": s.shop_name,
                "has_data": True,
                "period_start": str(snap.period_start) if snap.period_start else None,
                "period_end": str(snap.period_end) if snap.period_end else None,
                "gmv": str(shop_gmv),
                "net_revenue": str(shop_nr),
                "total_orders": shop_orders,
                "total_refunds": shop_refunds,
                "refund_rate": str(snap.refund_rate) if snap.refund_rate is not None else None,
                "subscription_tier": s.subscription_tier,
            }
        )

    agg_refund_rate = (
        str(Decimal(total_refunds) / Decimal(total_orders)) if total_orders > 0 else None
    )

    per_shop.sort(
        key=lambda x: Decimal(x.get("gmv", "0")) if x.get("has_data") else Decimal("0"),
        reverse=True,
    )

    return {
        "owner_id": str(shop.owner_id),
        "total_shops": len(shop_list),
        "shops_with_data": sum(1 for x in per_shop if x.get("has_data")),
        "aggregate": {
            "gmv_total": str(total_gmv),
            "net_revenue_total": str(total_net_revenue),
            "total_orders": total_orders,
            "total_refunds": total_refunds,
            "refund_rate": agg_refund_rate,
        },
        "shops": per_shop,
    }
