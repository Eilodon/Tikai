# Tikai

AI-powered P&L analytics for Vietnamese TikTok Shop sellers. Tikai parses platform CSV exports, calculates true profitability per SKU and creator, detects revenue leaks, and generates actionable Vietnamese-language recommendations backed by Claude.

**Version:** 2.0.2 | **Stack:** FastAPI · Next.js 15 · PostgreSQL · Redis · Anthropic API

---

## Features

- **P&L breakdown** — Net revenue per SKU/creator after platform commission, transaction fees, vouchers, refunds, and COGS
- **Time-aware fee config** — Correct fee rates applied per import period (handles mid-period fee changes)
- **Revenue leak detection** — Flags negative-margin SKUs, high-refund categories, low-ROI creators with confidence scores
- **AI action recommendations** — Claude explains each issue in Vietnamese and suggests a concrete next step
- **Weekly receipt** — Monday digest of completed actions and estimated savings
- **Settlement forecast** — Cash inflow projection over the next 14 days
- **COGS management** — Bulk upsert cost-of-goods to unlock true margin calculation
- **Recompute** — Re-run Rule Engine on existing orders after COGS update (Pro+)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x (asyncio), Alembic |
| Worker | ARQ (async Redis Queue), asyncio |
| Database | PostgreSQL 14+ |
| Cache / Queue | Redis 7+ |
| AI | Anthropic API — Claude Haiku 4.5 (fast tasks) + Sonnet 4.5 (clustering) |
| Auth | Supabase Auth (JWT) + shop-scoped authorization |
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
  /v1/imports      — upload CSV/XLSX → enqueue ARQ job
  /v1/insights     — latest snapshot, history, recompute
  /v1/actions      — list, complete, dismiss AI recommendations
  /v1/shops        — profile, COGS, notification settings
  /v1/weekly-receipts
  /v1/livestream
        │
        ├── Rule Engine
        │     fee_calculator · pl_calculator · leak_detector
        │     action_rules · settlement_calc · baselines
        │
        ├── AI Services (5 functions, all with sanitize→call→validate→fallback)
        │     import_rescue · aha_narrator · action_coach
        │     refund_clusterer · weekly_receipt
        │
        └── ARQ Worker (job_timeout=300s, max_jobs=10)
              process_import       — on demand (file upload)
              run_weekly_receipts  — cron Mon 08:00 VN
              verify_action_impact — on demand (7 days post-completion)
              cleanup_stuck_imports — cron every hour :05
        │
  ┌─────┴──────┬────────────┐
  PostgreSQL   Redis        Supabase
  (data)       (ARQ queue)  (auth + file storage)
```

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
cp .env.example .env   # or create manually — see Environment Variables section

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
SUPABASE_JWT_SECRET=...

# AI
ANTHROPIC_API_KEY=sk-ant-...

# CORS
ALLOWED_ORIGINS=["http://localhost:3000"]

# Email (optional — weekly digests)
SENDGRID_API_KEY=...
EMAIL_FROM_ADDRESS=noreply@tikai.vn

# Monitoring (optional)
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
pytest tests/ -m "not ai_eval" -v

# Backend — with coverage
pytest tests/ -m "not ai_eval" --cov=app --cov-report=term-missing

# Frontend
cd frontend
npm test              # run once
npm run test:watch    # watch mode
npm run test:coverage
```

### Linting & Type Checking

```bash
# Backend
cd backend
ruff check app/       # lint
ruff format app/      # format
mypy app/             # type check (informational — strict mode, continue-on-error in CI)

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
alembic upgrade head      # apply all pending
alembic current           # show current revision
alembic history           # full history
alembic downgrade -1      # undo last migration

# Create a new migration
alembic revision --autogenerate -m "add_column_x"
```

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
□ Worker service running (check Railway logs)
□ GET /healthz → {"status":"ok"}
□ GET /readyz  → {"status":"ready","db":"ok","redis":"ok"}
```

### Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Liveness probe — always 200 if process is alive |
| `GET /readyz` | Readiness probe — checks DB + Redis connectivity |
| `GET /health` | Legacy (kept for backward compat) |

---

## Key Design Decisions

**Time-aware fee config** — Orders are priced by their creation date. `process_import` and `recompute` both look up `FeeConfig` by `effective_from ≤ period_end ≤ effective_to`, not by current shop settings. This prevents historical recomputes from applying today's fee rates to last month's orders.

**Rule Engine never raises** — `process_import` wraps the entire job in a try/except that updates `ImportSession.status = "failed"` on any unhandled exception, so sellers always see a terminal state rather than a hung import.

**AI guardrail pipeline** — Every AI call follows: `sanitize_for_ai()` (PII mask + injection filter + `__tikai_data__` delimiter) → `call_ai()` → `validate_numbers_in_text()` (all numbers in output must exist in source JSON ±1%) → fallback template on validation failure. All 5 AI functions use this pattern.

**Atomic AI cost tracking** — Per-shop monthly budget ($0.50 default) is tracked in Redis with a Lua script that atomically checks + increments spend in one round-trip, preventing budget overruns under concurrent imports.

**Stable advisory lock keys** — `recompute_insight` uses `hashlib.md5(shop_id)` for PostgreSQL advisory lock keys. Python's `hash()` is randomized per process since 3.3 (PYTHONHASHSEED), which silently breaks cross-process locking in Railway's multi-replica deployments.

---

## Monitoring

**Stuck imports** — `cleanup_stuck_imports` runs every hour and marks sessions stuck in `processing` > 10min or `pending` > 20min as `failed`. Check `cleanup_stuck_imports.fixed` in logs if sellers report hung imports.

**AI budget** — Monitor `ai_cost_monthly_v2:{shop_id}` hash in Redis. Key TTL resets on the first of each month.

**AI hallucination rate** — `validate_numbers_in_text` logs `ai.invented_numbers` on failure. If this fires repeatedly for the same function, the model may be drifting.

**Shopee fee config** — Startup logs `startup.fee_config_missing` (CRITICAL) if no Shopee fee config exists. Without it, Shopee imports silently fall back to TikTok rates → wrong P&L.

---

## Changelog

| Version | Summary |
|---|---|
| 2.0.2 | Security hardening (XFF rate limit, IDOR guard, PII stripping), architectural fixes (connection pool, SQLAlchemy 2.x session lifecycle), financial logic fixes (margin VND vs ratio, COGS key normalization), AI safety (injection patterns, startup checks), async correctness (missing db.commit in verify_action_impact) |
| 2.0.1 | Shopee platform support, transaction_fee + order_processing_fee fields |
| 2.0.0 | Initial production release |

---

**License:** Proprietary — all rights reserved.
