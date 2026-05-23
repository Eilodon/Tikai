# Tikai

AI-powered P&L analytics for Vietnamese TikTok Shop, Shopee, and Lazada sellers. Tikai parses platform CSV/XLSX exports, calculates true profitability per SKU and creator, detects revenue leaks, tracks inventory, and generates actionable Vietnamese-language recommendations backed by Claude.

**Version:** 2.3.0 | **Stack:** FastAPI · Next.js 15 · PostgreSQL · Redis · Anthropic API

---

## Features

### P&L Engine
- **Full cost breakdown** — Net revenue per SKU/creator after platform commission, transaction fees (6% from 2026-05-09), order processing fee (3,000 VND/order from 2025-10-27), vouchers, shipping subsidies, refunds, and COGS
- **Time-aware fee config** — Correct fee rates applied per-order by `order_date` using `effective_from`/`effective_to` date ranges — mid-period fee changes apply correctly to each individual order, not retroactively to the whole batch
- **Multi-platform parsing** — TikTok Shop, Shopee, and Lazada exports parsed with platform-aware column alias dicts (EN + Vietnamese column names). Settlement exports parsed for cash reconciliation
- **COGS cascade for Shopee variants** — If a variation SKU (e.g. `SHIRT-RED`) has no COGS entry, automatically looks up its parent SKU (`SHIRT-100`) — no need to enter COGS for every color/size variant separately
- **Quantity-accurate COGS** — COGS is calculated as `cogs_per_unit × total_units_sold` (not order count), correctly handling multi-unit orders

### Analytics & Recommendations
- **Revenue leak detection** — Flags negative-margin SKUs, high-refund creators, voucher-driven losses, and commission-exceeds-margin SKUs with confidence scores
- **SKU Health Score** — Three-tier health classification (critical / warning / healthy) with drill-down reasons per SKU
- **Creator Scorecard** — Star / break-even / losing labels with suggested max commission rate per creator
- **Industry Benchmark** — Compare shop metrics (refund rate, margin %, fee burden %) against YouNet ECI 2025 benchmarks for 7 TikTok Shop categories (Pro+)
- **AI action recommendations** — Claude explains each issue in Vietnamese and suggests a concrete next step, with full guardrail pipeline (PII mask → injection filter → invented-number validation → fallback template)

### Inventory Tracking
- **Stock level management** — Set `stock_on_hand` per SKU via API; stored in `shop.stock_map` JSONB (no separate table)
- **Days-to-stockout forecast** — `days_to_stockout = stock_on_hand / avg_daily_units_sold_30d`; four statuses: `critical` (≤7 days), `warning` (≤14 days), `ok`, `no_stock_data`
- **Sell-rate from live orders** — Average computed from confirmed (non-refunded/cancelled) orders in the last 30 days — no manual input required
- **Priority sort** — `GET /v1/inventory/status` returns SKUs sorted critical-first so sellers see at-risk stock immediately (Pro+)

### Simulator & Planning Tools
- **What-If Simulator** — In-memory P&L delta for a single SKU: change affiliate rate, voucher rate, or price ±N% and see net revenue and margin impact instantly (no DB writes)
- **Campaign Pre-Check** — Multi-SKU campaign projector: enter planned units + rate overrides per SKU, get per-SKU and portfolio net revenue/margin projections before the campaign goes live
- **Price Recommender** — Reverse P&L: enter COGS + target margin → minimum viable selling price with full cost breakdown

### Data Management
- **COGS management** — Manual upsert via JSON or bulk CSV upload (`sku_id, cogs_per_unit`) with EN/VI column name support, per-row error reporting, 500-SKU cap
- **CSV Export** — Download full SKU P&L table from any snapshot as CSV (Pro+)
- **Misa-compatible export** — `GET /insights/{id}/export.csv?format=misa` returns Vietnamese column headers (Mã SKU, Doanh thu gộp, Giá vốn, Lợi nhuận gộp, Tỷ suất lợi nhuận %) matching the Misa accounting format — accountants can import directly (Pro+)
- **Recompute** — Re-run Rule Engine on existing orders after COGS update, no re-upload needed (Pro+)
- **Settlement parsing** — Parses TikTok settlement exports including `transaction_type`, `fee_amount`, `description`, `adjustment_type`, `seller_sku` for reconciliation

### Settlement Reconciliation
- **Payout reconciliation** — Upload TikTok settlement CSV to compare actual payout vs Rule Engine expected payout; verdict: `matched` / `minor_gap` / `major_gap` / `investigate` with Vietnamese action items
- **Hidden cost detection** — Automatically surfaces 4 cost categories often missed: shipping adjustments, refund admin fees, non-clawback commissions, reserve holds
- **SKU callout** — Flags which SKUs are generating the most shipping adjustment waste

### Creator CRM
- **Creator profiles** — Full CRUD (status, Zalo contact, internal note, negotiated rate) per creator linked to the shop
- **Auto-sync on import** — Every successful file import updates `creator_profiles` from the latest snapshot's `top_creators` data — no manual sync needed
- **Performance tracking** — GMV 30d, commission paid, revenue efficiency, refund rate, performance label (star / break_even / losing), suggested max commission rate
- **Commission waste alert** — Highlights commission already paid on subsequently-refunded orders (TikTok does not claw back)

### MCN & Multi-shop
- **MCN aggregate view** — `GET /v1/insights/aggregate` returns total GMV, net revenue, refund rate and per-shop breakdown across all shops owned by the same account (Business+)
- **Per-shop isolation** — Each shop has independent P&L, creators, COGS, and settings; row isolation enforced at JWT level
- **Multi-shop tiers** — Free: 1 shop, Pro: 3 shops, Business: 999 shops, Enterprise: 9,999 shops

### Notifications & Alerts
- **Daily Web Push** — ARQ cron at 08:15 VN time; sends browser push to shops with active subscription when a top leak exceeds 100,000 VND or any SKU is critical; Redis idempotency cap of 1 push per shop per day
- **Weekly email digest** — Monday P&L summary sent to `notification_email` via SendGrid; per-shop ARQ jobs with full fault isolation
- **Zalo ZNS scaffolding** — `send_zns_to_shop()` ready for production; activates automatically when `ZALO_OA_ID` and `ZALO_ZNS_ACCESS_TOKEN` are set; no-ops cleanly when absent
- **Cash Flow Timeline** — Settlement cash inflow forecast for next 14 / 30 days plus pending amount
- **Livestream ROI tracker** — Record host / studio / sample / ad costs per livestream session, update attributed GMV and orders post-live, compute live ROI and net ROI

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x (asyncio), Alembic |
| Worker | ARQ (async Redis Queue), asyncio |
| Database | PostgreSQL 14+ |
| Cache / Queue | Redis 7+ |
| AI | Anthropic API — Claude Haiku 4.5 (import rescue, narratives, coaching, receipts) + Sonnet 4.5 (refund clustering) |
| Auth | Supabase Auth (JWT) + shop-scoped row isolation |
| Storage | Supabase Storage (CSV/XLSX files) |
| Frontend | Next.js 15 (App Router), React 19, TanStack Query, Tailwind CSS 4 |
| Email | SendGrid |
| Monitoring | Sentry, structlog (JSON) |
| CI | GitHub Actions (lint · test · typecheck · vitest) |
| Deployment | Railway (API service + Worker service) |

---

## Architecture

```
Frontend (Next.js 15)
  pages: overview · import · actions · doi-soat · creators · livestream · settings
  auth:  Supabase SSR + middleware guards
        │
        │ REST/JSON (Bearer JWT)
        ▼
Backend (FastAPI)
  /v1/imports                              — upload CSV/XLSX → enqueue ARQ job (ARQ _job_id dedup)
  /v1/imports/{session_id}                 — poll status
  /v1/insights/latest                      — latest snapshot
  /v1/insights/history                     — week-over-week history (tier-capped: 4/12/52/104 weeks)
  /v1/insights/{id}                        — snapshot by ID
  /v1/insights/{id}/benchmark              — industry benchmark comparison (Pro+)
  /v1/insights/{id}/export.csv             — SKU P&L as CSV; ?format=misa for Misa-compatible output (Pro+)
  /v1/insights/recompute                   — re-run Rule Engine on existing orders (Pro+)
  /v1/insights/aggregate                   — cross-shop P&L aggregate for MCN/multi-brand (Business+)
  /v1/actions                              — list / complete / dismiss AI recommendations
  /v1/shops/me                             — shop profile + notification settings
  /v1/shops/me/notifications               — update email digest settings
  /v1/cogs                                 — get / upsert COGS per SKU
  /v1/cogs/bulk-import                     — bulk COGS upload via CSV
  /v1/inventory/set-stock                  — set stock_on_hand per SKU (Pro+)
  /v1/inventory/set-stock/{sku_id}         — DELETE a stock entry
  /v1/inventory/status                     — days-to-stockout per SKU, sorted critical-first (Pro+)
  /v1/tools/price-recommend                — reverse P&L: COGS + margin → min price
  /v1/tools/simulate                       — what-if P&L delta for 1 SKU (no DB writes)
  /v1/tools/simulate-campaign              — multi-SKU campaign pre-check (no DB writes)
  /v1/weekly-receipts                      — list / read receipts
  /v1/livestream                           — create / update / delete livestream sessions
  /v1/reconcile                            — settlement CSV reconciliation (Pro+)
  /v1/creators                             — list creator profiles with filter (Pro+)
  /v1/creators/{profile_id}                — get / update creator profile
  /v1/creators/sync                        — upsert creators from latest snapshot
        │
        ├── Rule Engine (app/services/rule_engine/)
        │     fee_calculator      — FeeConfigData, per-order config selection, net revenue calc
        │     pl_calculator       — GMV→Net Revenue, SKUSummary with total_quantity, CreatorSummary
        │     leak_detector       — negative margin, refund spike, creator ROI, voucher loss
        │     action_rules        — ActionTrigger generation from leak signals
        │     insight_builder     — InsightData assembly, top-N ranking, COGS coverage pct
        │     baselines           — category refund rate baselines (CATEGORY_REFUND_BASELINES)
        │     settlement_calc     — cash_in_14d, cash_in_30d, cash_pending_total
        │     settlement_reconciler — payout gap analysis, hidden cost detection, verdict
        │     price_recommender   — COGS + target margin → min price
        │     simulator           — single/multi-SKU what-if P&L delta
        │
        ├── Parsers (app/services/parser/)
        │     detector            — file type + platform detection (TikTok / Shopee / Lazada / unknown)
        │     normalizer          — column alias resolution (EN + VI names, per platform)
        │     order_parser        — parse_order_csv() (TikTok + Shopee + Lazada)
        │     settlement_parser   — parse_settlement_csv() (payout + extended fields)
        │     transaction_parser  — parse_transaction_csv()
        │
        ├── Creator CRM (app/services/creators/)
        │     sync                — sync_creators_from_snapshot() — upsert from top_creators_json
        │
        ├── Notifications (app/services/)
        │     push/web_push       — Web Push VAPID notifications
        │     zalo/zns_client     — Zalo ZNS send (no-op until credentials set)
        │
        ├── Benchmarks (app/services/benchmarks/)
        │     industry_data       — YouNet ECI 2025, 7 categories, versioned (BENCHMARK_VERSION)
        │
        ├── AI Services (app/services/ai/) — 5 functions, all tier-aware + guardrail pipeline
        │     import_rescue       — file format error diagnosis
        │     aha_narrator        — weekly business summary with key insight
        │     action_coach        — concrete next-step recommendation per action trigger
        │     refund_clusterer    — cluster refund reasons into ≤5 groups (Sonnet)
        │     weekly_receipt      — Monday savings digest with mandatory disclaimer check
        │
        └── ARQ Worker (job_timeout=300s, max_jobs=10)
              process_import                   — on demand (file upload); auto-syncs creator profiles
              trigger_weekly_receipts          — cron Mon 01:00 UTC (08:00 VN): enqueues per-shop jobs
              process_weekly_receipt_for_shop  — per-shop job (isolated, ARQ _job_id dedup)
              trigger_daily_alerts             — cron daily 01:15 UTC (08:15 VN): Web Push if critical signal
              verify_action_impact             — on demand, deferred 7 days post-completion
              cleanup_stuck_imports            — cron every hour :05 (marks stuck sessions failed)
        │
  ┌─────┴──────┬────────────┐
  PostgreSQL   Redis        Supabase
  (data,       (ARQ queue,  (auth + JWT
  18 migrations) AI budget,   + file storage)
               daily_alert
               idempotency)
```

---

## Subscription Tiers

| Feature | Free | Pro | Business | Enterprise |
|---|---|---|---|---|
| AI calls per import | 5 | 10 | 15 | 20 |
| AI monthly budget | $0.15 | $0.50 | $1.00 | $1.00 |
| History (weeks) | 4 | 12 | 52 | 104 |
| Shops | 1 | 3 | 999 | 9,999 |
| Re-analysis / Recompute | — | ✓ | ✓ | ✓ |
| Industry Benchmark | — | ✓ | ✓ | ✓ |
| CSV Export | — | ✓ | ✓ | ✓ |
| Misa Export | — | ✓ | ✓ | ✓ |
| Settlement Reconciliation | — | ✓ | ✓ | ✓ |
| Creator CRM | — | ✓ | ✓ (full) | ✓ (full) |
| Inventory Tracking | — | ✓ | ✓ | ✓ |
| Daily Web Push Alerts | ✓ | ✓ | ✓ | ✓ |
| Zalo ZNS Notifications | — | ✓ | ✓ | ✓ |
| Shopee / Lazada import | — | ✓ | ✓ | ✓ |
| MCN Aggregate View | — | — | ✓ | ✓ |

> Enterprise tier targets MCN operators and multi-brand agencies managing large creator/shop portfolios.

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 14+
- Redis 7+

### Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"

# Copy and fill environment variables
cp .env.example .env   # see Environment Variables section below

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000

# In a separate terminal: start ARQ worker
python -m arq app.tasks.worker.WorkerSettings
```

### Frontend

```bash
cd frontend

npm install

cp .env.example .env.local   # fill NEXT_PUBLIC_API_URL + Supabase credentials

npm run dev   # http://localhost:3000
```

---

## Environment Variables

All backend config lives in `backend/app/core/config.py` (Pydantic Settings). Required fields:

```env
# App
ENVIRONMENT=development          # development | staging | production
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tikai
REDIS_URL=redis://localhost:6379

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...          # min 32 chars

# AI
ANTHROPIC_API_KEY=sk-ant-...

# AI monthly budget by tier (USD, Decimal strings)
AI_MAX_COST_PER_MONTH_USD_FREE=0.15
AI_MAX_COST_PER_MONTH_USD_PRO=0.50
AI_MAX_COST_PER_MONTH_USD_BUSINESS=1.00

# CORS (In staging/production, must not point to localhost)
ALLOWED_ORIGINS=["http://localhost:3000"]

# Email — optional, required for weekly digest emails
SENDGRID_API_KEY=...
EMAIL_FROM_ADDRESS=noreply@tikai.vn
APP_BASE_URL=https://app.tikai.vn # Set to https://staging.tikai.vn for staging

# Web Push — optional, required for daily push alerts
VAPID_PRIVATE_KEY=...
VAPID_PUBLIC_KEY=...
VAPID_CLAIMS_EMAIL=admin@tikai.vn

# Zalo ZNS — optional, feature disables cleanly when absent
ZALO_OA_ID=...
ZALO_ZNS_ACCESS_TOKEN=...

# Monitoring (Required in staging/production)
SENTRY_DSN=https://xxx@sentry.io/123456

# Admin API — optional
ADMIN_SECRET=...                 # Min 16 chars if set
```

> [!IMPORTANT]
> **Production & Staging Validation Safeguards (Fail-Fast):**
> 1. `SENTRY_DSN` is strictly required in `production` and `staging`.
> 2. `DATABASE_URL` must include SSL parameter (`sslmode=require` or `ssl=true`) in `production` and `staging` to protect customer data.
> 3. `ALLOWED_ORIGINS` cannot contain `localhost` in `production` or `staging`.
> 4. `APP_BASE_URL` must not be set to the production default (`app.tikai.vn`) when in `staging` environment.

Frontend (`.env.local`):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

---

## Development

### Tests

```bash
# Backend — unit tests only (no DB, no AI calls required)
cd backend
python3.12 -m pytest tests/ -v

# With coverage
python3.12 -m pytest tests/ --cov=app --cov-report=term-missing
```

### Linting & Type Checking

```bash
# Backend
cd backend
ruff check app/       # lint
ruff format app/      # format
mypy app/             # type check (strict mode, informational in CI)

# Frontend
cd frontend
npm run lint          # ESLint
npm run type-check    # tsc --noEmit
```

### Generating Frontend API Types

```bash
cd frontend
npm run generate-types   # reads /openapi.json from running backend
```

### Migrations

```bash
cd backend
alembic upgrade head           # apply all pending
alembic current                # show current revision
alembic history                # full history
alembic downgrade -1           # undo last migration
alembic revision --autogenerate -m "add_column_x"   # create new
```

There are currently **18 migrations** (0001–0018). Migration env uses `pg_advisory_lock` to prevent concurrent execution across multiple replicas — only one process runs migrations at a time; others wait then detect no pending work.

---

## Deployment (Railway)

### Services

| Service | Build | Start command |
|---|---|---|
| API | `Dockerfile.prod` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2` |
| Worker | `Dockerfile.prod` | `python -m arq app.tasks.worker.WorkerSettings` |

### Pre-deploy Checklist

```
□ alembic upgrade head ran against production DB (migrations 0001–0018)
□ ALLOWED_ORIGINS set to production frontend URL
□ ANTHROPIC_API_KEY configured
□ SENTRY_DSN configured
□ VAPID_PRIVATE_KEY + VAPID_PUBLIC_KEY configured for Web Push (optional but recommended)
□ ZALO_OA_ID + ZALO_ZNS_ACCESS_TOKEN set if Zalo ZNS is required (optional)
□ Worker service running (check Railway logs for trigger_weekly_receipts + trigger_daily_alerts crons)
□ GET /healthz → {"status":"ok","version":"2.3.0"}
□ GET /readyz  → {"status":"ready","db":"ok","redis":"ok"}
```

### Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Liveness probe — always 200 if process is alive |
| `GET /readyz` | Readiness probe — checks DB + Redis connectivity; 503 if either fails |
| `GET /health` | Legacy alias (kept for backward compat) |

---

## Key Design Decisions

**Per-order fee config selection** — `select_fee_config_for_date(order_date, configs)` picks the correct `FeeConfigData` for each order using `effective_from`/`effective_to` date ranges. `process_import` and `recompute` load all configs that overlap the import period and apply them per-row — a mid-period rate change (e.g. 12.5% → 14.5% on May 11) applies to May 11+ orders only, not retroactively to the whole batch. Combined version string (`v1+v2`) is stored in the snapshot for auditability.

**COGS uses total_quantity, not order_count** — `pl_calculator` tracks `total_quantity` (sum of `row.quantity` across all rows for an SKU) separately from `order_count`. Simulator and recompute use `total_quantity` for COGS calculation. One order with 3 units costs 3× COGS, not 1×.

**COGS cascade for Shopee variants** — `RawOrderRow` includes `parent_sku_id` (populated from "Parent SKU Reference No." / "Mã SKU cha" columns). `pl_calculator` checks `cogs_map[sku_id]` first, falls back to `cogs_map[parent_sku_id]` if not found. Variation-specific COGS takes precedence when both exist.

**Inventory sell-rate window** — `GET /v1/inventory/status` uses a fixed 30-day lookback (`_LOOKBACK_DAYS = 30`) against confirmed (non-cancelled/refunded) orders. Changing the window changes the sell-rate denominator; the constant is intentionally named and isolated in `inventory.py` for easy adjustment.

**Platform-aware column resolution** — `build_column_map(headers, platform)` selects among three alias dicts: `COLUMN_ALIASES` (TikTok), `SHOPEE_COLUMN_ALIASES`, and `LAZADA_COLUMN_ALIASES`. `detect_file_type()` returns the platform as the third element of its 3-tuple return so the parser can pass it directly to `build_column_map` — no second-guessing required downstream.

**Worker per-shop isolation** — `trigger_weekly_receipts` (cron) queries all active shops and enqueues one `process_weekly_receipt_for_shop(shop_id, week_label)` job per shop. Each job runs in its own ARQ slot with full `job_timeout=300s`. One shop failing doesn't affect others. `_job_id = "weekly-receipt-{shop_id}-{week_label}"` prevents duplicate processing if the cron re-fires (e.g. after worker restart).

**ARQ _job_id deduplication** — `POST /imports` passes `_job_id=str(session.id)` to `enqueue_job()`. Re-uploading the same file (same SHA-256 hash → same session) returns the existing session ID; the ARQ job is a no-op if already queued or running.

**AI guardrail pipeline** — Every AI call follows: `sanitize_for_ai()` (PII mask + injection filter + `__tikai_data__` delimiter) → `call_ai(tier=tier)` → `validate_numbers_in_text()` (all numbers in output must exist in source JSON ±1%) → fallback template on validation failure or after 2 attempts. `asyncio.sleep(2s)` before the second attempt to avoid rate-limit burst.

**Tier-aware AI budget** — `_check_budget(shop_id, tier)` reads `settings.ai_budget_for_tier(tier)` (configurable via env vars, default $0.15/$0.50/$1.00 for free/pro/business). Budget is tracked in Redis key `ai_cost_monthly_v2:{shop_id}` with a Lua script that atomically checks + records spend in one round-trip. Key resets monthly via TTL.

**Stable advisory lock keys** — `recompute_insight` uses `hashlib.md5(shop_id)` for PostgreSQL advisory lock keys. Python's `hash()` is randomized per process (PYTHONHASHSEED), which would silently break cross-process locking in multi-replica deployments. `hashlib` is deterministic.

**Migration concurrency** — `migrations/env.py` calls `SELECT pg_advisory_lock(8765432187654321)` before running any migration and releases it in a `finally` block. All replicas starting simultaneously will serialize — only one runs the migration; others wait and then find no pending work.

**Rule Engine never raises** — `process_import` wraps the entire job in a try/except that updates `ImportSession.status = "failed"` on any unhandled exception. Sellers always see a terminal state (completed or failed), never a hung import.

**Benchmark versioning** — `BenchmarkComparison` includes `benchmark_version` (e.g. `"2025-Q1"`) and `last_updated` (date) in every comparison result. When YouNet releases updated data, bump `BENCHMARK_VERSION` and `LAST_UPDATED` in `industry_data.py` — clients can detect stale cached comparisons.

---

## Monitoring

**Stuck imports** — `cleanup_stuck_imports` runs every hour at :05 and marks `ImportSession` records stuck in `processing > 10min` or `pending > 20min` as `failed`. Check `cleanup_stuck_imports.fixed` in logs if sellers report hung imports.

**AI budget** — Monitor `ai_cost_monthly_v2:{shop_id}` hash in Redis. Key TTL resets on the first of each month. `_check_budget` logs `ai.budget_exceeded` when a call is blocked.

**AI hallucination rate** — `validate_numbers_in_text` logs `ai.invented_numbers` on validation failure. Repeated failures for the same function indicate model drift or prompt regression.

**Shopee / Lazada fee config** — Startup logs `startup.fee_config_missing` (CRITICAL level) if no Shopee `FeeConfig` exists in the DB. Without it, Shopee/Lazada imports silently fall back to TikTok rates → wrong P&L. `recompute_insight` logs `recompute_insight.no_platform_fee_config` (WARNING) on fallback. Ensure a Lazada fee config row exists in `fee_configs` before enabling Lazada imports in production.

**Weekly receipts** — `trigger_weekly_receipts` logs `weekly_receipts.trigger.done` with `enqueued=N`. Each shop job logs `weekly_receipt_for_shop.done` on success or `weekly_receipt_for_shop.no_actions` if the shop had no completed actions. Check for `weekly_receipt_for_shop.shop_not_found` if jobs are being enqueued for deleted shops.

---

## Changelog

| Version | Summary |
|---|---|
| 2.3.0 | **Lazada CSV parser** — EN + VI fingerprints + `LAZADA_COLUMN_ALIASES`; platform auto-detected, 3rd sàn supported. **Inventory tracking** — `POST /v1/inventory/set-stock`, `GET /v1/inventory/status` with days-to-stockout from 30-day sell rate; `stock_map` JSONB on Shop model; migration 0018. **MCN aggregate view** — `GET /v1/insights/aggregate` cross-shop P&L for Business+ (GMV, net revenue, refund rate with per-shop breakdown). **Enterprise tier** — 9,999 shops, 2-year history, 20 AI calls/import; `MCN_AGGREGATE` feature gate. **Misa export** — `?format=misa` on export endpoint returns Vietnamese accounting headers compatible with Misa import. Pricing messages updated to 299k/799k/month. |
| 2.2.0 | Settlement reconciliation (`POST /v1/reconcile`, `/doi-soat` page). Creator CRM (`/creators` page, auto-sync on import). Daily Web Push alerts (ARQ cron, Redis idempotency). Zalo ZNS scaffolding. WowScreen 3-way conditional. Quantified COGS nudge in Overview. Nav: Creators + Đối soát links. 17 new unit tests. |
| 2.1.0 | BUG-SIM-01: simulator now uses `total_quantity` (units sold) instead of `order_count` for COGS. Settlement parser extended with `transaction_type`, `fee_amount`, `description`, `adjustment_type`, `seller_sku` columns. Worker converted to per-shop ARQ jobs (`trigger_weekly_receipts` + `process_weekly_receipt_for_shop`). New: `GET /insights/{id}/export.csv` (CSV export, Pro+), `POST /tools/simulate-campaign` (multi-SKU campaign pre-check), `POST /cogs/bulk-import` (CSV COGS upload). |
| 2.0.2 | Per-order FeeConfig selection (mid-period fee changes apply per-row, not retroactively). Shopee COGS cascade (parent→variation SKU lookup). Benchmark versioning (`benchmark_version` + `last_updated` in API). Tier-aware AI budget ($0.15/$0.50/$1.00 for free/pro/business). Migration `pg_advisory_lock` for multi-replica safety. ARQ `_job_id` dedup on import enqueue. SKU Health Score, Creator Scorecard, What-If Simulator, Price Recommender, Industry Benchmark, Cash Flow Timeline. |
| 2.0.1 | Shopee platform support (parser, platform-aware column aliases, fee config). `transaction_fee` + `order_processing_fee` fields on orders and FeeConfig. |
| 2.0.0 | Initial production release. |

---

**License:** Proprietary — all rights reserved.
