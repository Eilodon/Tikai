# Tikai

AI-powered P&L analytics for Vietnamese TikTok Shop and Shopee sellers. Tikai parses platform CSV/XLSX exports, calculates true profitability per SKU and creator, detects revenue leaks, and generates actionable Vietnamese-language recommendations backed by Claude.

**Version:** 2.0.2 | **Stack:** FastAPI · Next.js 15 · PostgreSQL · Redis · Anthropic API

---

## Features

### P&L Engine
- **Full cost breakdown** — Net revenue per SKU/creator after platform commission, transaction fees (6% from 2026-05-09), order processing fee (3,000 VND/order from 2025-10-27), vouchers, shipping subsidies, refunds, and COGS
- **Time-aware fee config** — Correct fee rates applied per-order by `order_date` using `effective_from`/`effective_to` date ranges — mid-period fee changes apply correctly to each individual order, not retroactively to the whole batch
- **Multi-platform parsing** — TikTok and Shopee exports parsed with platform-aware column alias dicts (EN + Vietnamese column names). Settlement exports parsed for cash reconciliation
- **COGS cascade for Shopee variants** — If a variation SKU (e.g. `SHIRT-RED`) has no COGS entry, automatically looks up its parent SKU (`SHIRT-100`) — no need to enter COGS for every color/size variant separately
- **Quantity-accurate COGS** — COGS is calculated as `cogs_per_unit × total_units_sold` (not order count), correctly handling multi-unit orders

### Analytics & Recommendations
- **Revenue leak detection** — Flags negative-margin SKUs, high-refund creators, voucher-driven losses, and commission-exceeds-margin SKUs with confidence scores
- **SKU Health Score** — Three-tier health classification (critical / warning / healthy) with drill-down reasons per SKU
- **Creator Scorecard** — Star / break-even / losing labels with suggested max commission rate per creator
- **Industry Benchmark** — Compare shop metrics (refund rate, margin %, fee burden %) against YouNet ECI 2025 benchmarks for 7 TikTok Shop categories (Pro+)
- **AI action recommendations** — Claude explains each issue in Vietnamese and suggests a concrete next step, with full guardrail pipeline (PII mask → injection filter → invented-number validation → fallback template)

### Simulator & Planning Tools
- **What-If Simulator** — In-memory P&L delta for a single SKU: change affiliate rate, voucher rate, or price ±N% and see net revenue and margin impact instantly (no DB writes)
- **Campaign Pre-Check** — Multi-SKU campaign projector: enter planned units + rate overrides per SKU, get per-SKU and portfolio net revenue/margin projections before the campaign goes live
- **Price Recommender** — Reverse P&L: enter COGS + target margin → minimum viable selling price with full cost breakdown

### Data Management
- **COGS management** — Manual upsert via JSON or bulk CSV upload (`sku_id, cogs_per_unit`) with EN/VI column name support, per-row error reporting, 500-SKU cap
- **CSV Export** — Download full SKU P&L table from any snapshot as CSV (Pro+)
- **Recompute** — Re-run Rule Engine on existing orders after COGS update, no re-upload needed (Pro+)
- **Settlement parsing** — Parses TikTok settlement exports including `transaction_type`, `fee_amount`, `description`, `adjustment_type`, `seller_sku` for reconciliation

### Receipts & Scheduling
- **Weekly receipt** — Monday digest of completed actions and estimated savings, generated per-shop via isolated ARQ jobs (each shop has independent timeout and fault isolation)
- **Email digest** — Weekly receipt sent to `notification_email` via SendGrid; delivery tracked in DB; opt-in per shop
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
  pages: overview · import · actions · livestream · settings
  auth:  Supabase SSR + middleware guards
        │
        │ REST/JSON (Bearer JWT)
        ▼
Backend (FastAPI)
  /v1/imports                              — upload CSV/XLSX → enqueue ARQ job (ARQ _job_id dedup)
  /v1/imports/{session_id}                 — poll status
  /v1/insights/latest                      — latest snapshot
  /v1/insights/history                     — week-over-week history (tier-capped: 4/12/52 weeks)
  /v1/insights/{id}                        — snapshot by ID
  /v1/insights/{id}/benchmark              — industry benchmark comparison (Pro+)
  /v1/insights/{id}/export.csv             — export SKU P&L as CSV (Pro+)
  /v1/insights/recompute                   — re-run Rule Engine on existing orders (Pro+)
  /v1/actions                              — list / complete / dismiss AI recommendations
  /v1/shops/me                             — shop profile + notification settings
  /v1/cogs                                 — get / upsert COGS per SKU
  /v1/cogs/bulk-import                     — bulk COGS upload via CSV
  /v1/tools/price-recommend                — reverse P&L: COGS + margin → min price
  /v1/tools/simulate                       — what-if P&L delta for 1 SKU (no DB writes)
  /v1/tools/simulate-campaign              — multi-SKU campaign pre-check (no DB writes)
  /v1/weekly-receipts                      — list / read receipts
  /v1/livestream                           — create / update / delete livestream sessions
        │
        ├── Rule Engine (app/services/rule_engine/)
        │     fee_calculator  — FeeConfigData, per-order config selection, net revenue calc
        │     pl_calculator   — GMV→Net Revenue, SKUSummary with total_quantity, CreatorSummary
        │     leak_detector   — negative margin, refund spike, creator ROI, voucher loss
        │     action_rules    — ActionTrigger generation from leak signals
        │     insight_builder — InsightData assembly, top-N ranking, COGS coverage pct
        │     baselines       — category refund rate baselines (CATEGORY_REFUND_BASELINES)
        │     settlement_calc — cash_in_14d, cash_in_30d, cash_pending_total
        │     price_recommender — COGS + target margin → min price
        │     simulator       — single/multi-SKU what-if P&L delta
        │
        ├── Parsers (app/services/parser/)
        │     detector        — file type + platform detection (TikTok / Shopee / unknown)
        │     normalizer      — column alias resolution (EN + VI names, per platform)
        │     order_parser    — parse_order_csv() (TikTok + Shopee)
        │     settlement_parser — parse_settlement_csv() (payout + extended fields)
        │     transaction_parser — parse_transaction_csv()
        │
        ├── Benchmarks (app/services/benchmarks/)
        │     industry_data   — YouNet ECI 2025, 7 categories, versioned (BENCHMARK_VERSION)
        │
        ├── AI Services (app/services/ai/) — 5 functions, all tier-aware + guardrail pipeline
        │     import_rescue   — file format error diagnosis
        │     aha_narrator    — weekly business summary with key insight
        │     action_coach    — concrete next-step recommendation per action trigger
        │     refund_clusterer — cluster refund reasons into ≤5 groups (Sonnet)
        │     weekly_receipt  — Monday savings digest with mandatory disclaimer check
        │
        └── ARQ Worker (job_timeout=300s, max_jobs=10)
              process_import              — on demand (file upload)
              trigger_weekly_receipts     — cron Mon 01:00 UTC (08:00 VN): enqueues per-shop jobs
              process_weekly_receipt_for_shop — per-shop job (isolated, ARQ _job_id dedup)
              verify_action_impact        — on demand, deferred 7 days post-completion
              cleanup_stuck_imports       — cron every hour :05 (marks stuck sessions failed)
        │
  ┌─────┴──────┬────────────┐
  PostgreSQL   Redis        Supabase
  (data,       (ARQ queue,  (auth + JWT
  8 migrations) AI budget)   + file storage)
```

---

## Subscription Tiers

| Feature | Free | Pro | Business |
|---|---|---|---|
| AI calls per import | 3 | 10 | 15 |
| AI monthly budget | $0.15 | $0.50 | $1.00 |
| History (weeks) | 4 | 12 | 52 |
| Shops | 1 | 3 | 999 |
| Re-analysis / Recompute | — | ✓ | ✓ |
| Industry Benchmark | — | ✓ | ✓ |
| CSV Export | — | ✓ | ✓ |
| Creator CRM | — | basic | full |
| Shopee / Lazada import | — | — | ✓ |
| Zalo OA Push | — | ✓ | ✓ |

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
ENVIRONMENT=development          # development | production
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

# CORS
ALLOWED_ORIGINS=["http://localhost:3000"]

# Email — optional, required for weekly digest emails
SENDGRID_API_KEY=...
EMAIL_FROM_ADDRESS=noreply@tikai.vn

# Monitoring — optional
SENTRY_DSN=https://xxx@sentry.io/123456
```

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

There are currently **8 migrations** (0001–0008). Migration env uses `pg_advisory_lock` to prevent concurrent execution across multiple replicas — only one process runs migrations at a time; others wait then detect no pending work.

---

## Deployment (Railway)

### Services

| Service | Build | Start command |
|---|---|---|
| API | `Dockerfile.prod` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2` |
| Worker | `Dockerfile.prod` | `python -m arq app.tasks.worker.WorkerSettings` |

### Pre-deploy Checklist

```
□ alembic upgrade head ran against production DB
□ ALLOWED_ORIGINS set to production frontend URL
□ ANTHROPIC_API_KEY configured
□ SENTRY_DSN configured
□ Worker service running (check Railway logs for trigger_weekly_receipts cron)
□ GET /healthz → {"status":"ok","version":"2.0.2"}
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

**Shopee fee config** — Startup logs `startup.fee_config_missing` (CRITICAL level) if no Shopee `FeeConfig` exists in the DB. Without it, Shopee imports silently fall back to TikTok rates → wrong P&L. `recompute_insight` logs `recompute_insight.no_platform_fee_config` (WARNING) on fallback.

**Weekly receipts** — `trigger_weekly_receipts` logs `weekly_receipts.trigger.done` with `enqueued=N`. Each shop job logs `weekly_receipt_for_shop.done` on success or `weekly_receipt_for_shop.no_actions` if the shop had no completed actions. Check for `weekly_receipt_for_shop.shop_not_found` if jobs are being enqueued for deleted shops.

---

## Changelog

| Version | Summary |
|---|---|
| latest | BUG-SIM-01: simulator now uses `total_quantity` (units sold) instead of `order_count` for COGS. Settlement parser extended with `transaction_type`, `fee_amount`, `description`, `adjustment_type`, `seller_sku` columns. Worker converted to per-shop ARQ jobs (`trigger_weekly_receipts` + `process_weekly_receipt_for_shop`). New: `GET /insights/{id}/export.csv` (CSV export, Pro+), `POST /tools/simulate-campaign` (multi-SKU campaign pre-check), `POST /cogs/bulk-import` (CSV COGS upload). |
| 2.0.2 | Per-order FeeConfig selection (mid-period fee changes apply per-row, not retroactively). Shopee COGS cascade (parent→variation SKU lookup). Benchmark versioning (`benchmark_version` + `last_updated` in API). Tier-aware AI budget ($0.15/$0.50/$1.00 for free/pro/business). Migration `pg_advisory_lock` for multi-replica safety. ARQ `_job_id` dedup on import enqueue. SKU Health Score, Creator Scorecard, What-If Simulator, Price Recommender, Industry Benchmark, Cash Flow Timeline. Security hardening (XFF rate limit, IDOR guard, PII stripping), architectural fixes (connection pool, SQLAlchemy 2.x session lifecycle), financial logic fixes (margin denominator, COGS key normalization), AI safety (injection patterns, startup checks). |
| 2.0.1 | Shopee platform support (parser, platform-aware column aliases, fee config). `transaction_fee` + `order_processing_fee` fields on orders and FeeConfig. |
| 2.0.0 | Initial production release. |

---

**License:** Proprietary — all rights reserved.
