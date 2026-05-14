# Tikai — AI-Powered P&L Insights for TikTok Shop Vietnam

Tikai helps Vietnamese TikTok Shop sellers understand their profitability, detect revenue leaks, and take actionable steps to improve margins — all powered by AI analysis and automated insights.

**Status:** Production-ready (v2.0.2) | **Tier:** Tier 3 Financial SaaS | **Multi-tenant** | **PII-safe**

---

## Features

### 📊 Intelligent P&L Analysis
- **Automatic fee detection** — Parses platform commissions, transaction fees, order processing fees from CSV exports
- **Cost breakdown** — Tracks vouchers, shipping subsidies, refunds per order
- **Net revenue calculation** — Accurate profitability per SKU, creator, and category
- **Time-aware fee config** — Applies correct fees based on import date (handles fee changes mid-period)

### 🎯 AI-Driven Action Engine
- **Revenue leak detection** — Identifies unprofitable SKUs, high-refund categories, low-ROI creators
- **Confidence scoring** — High/Medium/Low confidence on each recommendation
- **Action Coach** — Explains why, what to do, expected impact in Vietnamese
- **Settlement forecast** — Projects cash inflow over 14 days

### 📱 Seller Dashboard
- **Weekly digests** — Email summaries of completed actions + projected savings
- **Action tracking** — Mark actions as done, dismiss, confirm actual impact
- **COGS management** — Input cost-of-goods to calculate true margins
- **Insight history** — Week-over-week P&L comparison (4 weeks)

### 🔐 Enterprise Security
- **PII protection** — Masks buyer names, addresses, phone numbers in AI processing
- **Prompt injection defense** — Detects jailbreak attempts in both English and Vietnamese
- **Rate limiting** — Per-IP throttling (200/min default, shop-aware overrides available)
- **Secret scanning** — No hardcoded API keys, JWT secrets from environment only
- **IDOR invariants** — All queries filtered by shop_id at the database layer

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL + SQLAlchemy ORM
- **Cache:** Redis (ARQ for background tasks)
- **File storage:** Supabase Storage (S3-compatible)
- **AI:** Claude Sonnet 4.5 + Haiku 4.5 (Anthropic API)
- **Auth:** Supabase Auth (JWT) + Custom shop_id authorization
- **Async:** asyncio, ARQ worker pool

### Frontend
- **Framework:** Next.js 15 (App Router, Server Components)
- **Styling:** Tailwind CSS 4.0
- **State:** TanStack React Query (cached queries, optimistic updates)
- **Auth:** Supabase SSR client + middleware guards
- **Charts:** Recharts (weekly trends, P&L visualization)
- **Testing:** Vitest + React Testing Library + MSW

### DevOps
- **Containerization:** Docker (multi-stage, non-root user)
- **Orchestration:** Railway (backend + worker services)
- **CI/CD:** Git-based (push to deploy)
- **Monitoring:** Sentry (error tracking)
- **Database:** PostgreSQL on Railway

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                     │
│  Pages: Overview, Import, Actions, Settings, Livestream    │
│  Hooks: useLatestInsight, useActions, useImportStatus      │
│  API Client: Retry logic, 401 token refresh, error mapping │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ (FastAPI + JSON)
┌──────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
├──────────────────────────────────────────────────────────────┤
│ Auth Layer                                                   │
│  └─ JWT from Supabase + shop_id from request context       │
│                                                              │
│ API Routes                                                   │
│  ├─ /v1/imports/* — File upload → ARQ enqueue              │
│  ├─ /v1/insights/* — Latest + history, recompute           │
│  ├─ /v1/actions/* — List, complete, dismiss                │
│  ├─ /v1/shops/* — Shop settings, COGS, notifications       │
│  └─ /v1/livestream/* — Live ROI tracking                   │
│                                                              │
│ Rule Engine (Insight Builder)                              │
│  ├─ Fee Config (time-aware, effective_from/to dates)      │
│  ├─ Cost Calculator (transaction_fee, order_processing_fee)│
│  ├─ Insight Builder (159 lines, never raises)              │
│  ├─ Baselines (refund rates per category)                  │
│  └─ Settlement Forecast (cash_in_14d)                      │
│                                                              │
│ AI Services                                                 │
│  ├─ ImportRescue — Fix malformed CSVs                      │
│  ├─ AhaNarrator — Narrative P&L summary                    │
│  ├─ ActionCoach — Per-action recommendations               │
│  └─ Cost Tracking — Atomic Lua script (no race conditions) │
│                                                              │
│ Data Layer                                                   │
│  ├─ Alembic migrations (0001–0007)                         │
│  ├─ Models: Shop, Order, ImportSession, InsightSnapshot   │
│  ├─ Models: AIAction, WeeklyReceipt, FeeConfig, LiveStream │
│  └─ Indexes: ix_orders_shop_id_sku_name, etc              │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
    PostgreSQL      Redis        Supabase
    (PG 14+)      (ARQ pool)    (Auth + Storage)
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase keys, Anthropic API key, etc.

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start ARQ worker
python -m arq app.tasks.worker.WorkerSettings
```

### Frontend Setup

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with API URL + Supabase credentials

# Start dev server
npm run dev
# Open http://localhost:3000
```

### Database Migrations

```bash
# View pending migrations
alembic current
alembic history

# Run specific migration
alembic upgrade +2  # Run next 2 pending migrations

# Downgrade
alembic downgrade -1  # Undo last migration
```

---

## Development Workflow

### Running Tests

**Backend:**
```bash
cd backend
pytest tests/                    # All tests
pytest tests/test_idor.py       # IDOR invariants only
pytest -v --tb=short           # Verbose output
```

**Frontend:**
```bash
cd frontend
npm test                         # Run all tests
npm run test:watch             # Watch mode
npm run test:coverage          # Coverage report
```

### Code Quality

**Backend:**
```bash
black app/                      # Format
flake8 app/                     # Lint
mypy app/                       # Type check
```

**Frontend:**
```bash
npm run lint                    # ESLint
npm run type-check             # TypeScript check
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes, commit
git add .
git commit -m "Brief description of what changed

Detailed explanation if needed.

https://claude.ai/code/session_..."

# Push and create PR
git push -u origin feature/your-feature
```

---

## Deployment

### Environment Variables

**Backend (.env):**
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@host:5432/tikai
REDIS_URL=redis://host:6379
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
SENTRY_DSN=https://xxx@sentry.io/123456
ALLOWED_ORIGINS=["https://app.tikai.vn"]
```

**Frontend (.env.production):**
```env
NEXT_PUBLIC_API_URL=https://api.tikai.vn
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

### Railway Deployment

1. **Backend Service:**
   - Build: Dockerfile.prod
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
   - Set environment variables (SENTRY_DSN, ALLOWED_ORIGINS, etc.)

2. **Worker Service:**
   - Build: Dockerfile.prod
   - Start command: `python -m arq app.tasks.worker.WorkerSettings`
   - Config: railway.worker.json

3. **Database:**
   - PostgreSQL 14+
   - Run migrations: `alembic upgrade head`

4. **Staging Checklist:**
   ```
   ✅ ALLOWED_ORIGINS set to https://app.tikai.vn
   ✅ SENTRY_DSN configured
   ✅ ANTHROPIC_API_KEY set
   ✅ Migrations ran (alembic upgrade head)
   ✅ Worker service running + monitoring
   ✅ Health check: GET /healthz → 200 OK
   ```

---

## Key Design Decisions

### 1. Time-Aware Fee Configuration
Orders are charged fees based on when they were created, not when imported. Migration 0006 inserts a new 2025-VN-v2 fee config with effective_to dates, ensuring historical imports use correct rates.

**Code:** `process_import.py:145-157`

### 2. Never-Raise Background Tasks
The `process_import` function has an outer try/except that catches ALL exceptions and updates the session status to `failed` rather than raising. This prevents hung imports and ensures the user always sees a terminal state.

**Code:** `process_import.py:376-401`

### 3. Atomic Cost Recording (Lua Script)
AI cost tracking uses a Redis Lua script to atomically increment total spend + call count in a single round-trip, preventing race conditions between concurrent imports.

**Code:** `client.py:48-57`

### 4. Per-IP Rate Limiting with NAT Trade-off
Rate limiting is per-IP (not per-shop) to avoid complex Redis key management. This is documented as an acceptable trade-off for MVP; post-launch we can implement per-shop limits if abuse detected.

**Code:** `rate_limit.py:25-29`

### 5. PII Masking + Prompt Injection Defense
Before sending order data to Claude, we mask buyer names/addresses and strip prompt injection patterns. Additionally, camelCase field names are normalized to snake_case to catch PII bypass attempts.

**Code:** `guardrails.py:176-208`

---

## Monitoring & Debugging

### Health Checks
```bash
# Backend health
curl http://localhost:8000/healthz

# Database connection
curl http://localhost:8000/health/db

# Redis connection (via ARQ pool test)
# Check logs for "arq.pool_dead_recreating"
```

### Logs
- **Backend:** Structured logging with structlog (JSON format in production)
- **Frontend:** Console logs in dev, Sentry in production
- **Worker:** ARQ logs + custom import task logs

### Common Issues

**Import stuck in "processing":**
- Check ARQ worker is running: `ps aux | grep arq`
- Check Redis connection: `redis-cli ping`
- Worker will auto-mark as failed if > 10min (cleanup_stuck_imports cron)

**"AI budget exceeded" error:**
- Check HGET ai_cost_monthly_v2:{shop_id} total_usd in Redis
- TTL resets monthly (calendar month, not rolling 30d)

**CORS errors on frontend:**
- Verify ALLOWED_ORIGINS in backend env vars
- Check middleware whitelist in `middleware.ts`

---

## Testing Strategy

### Test Pyramid
```
                 ▲
               /   \
              /  E2E \     (Optional: Playwright)
             /________\
            /          \
           /  Integration\  (ImportPage, OverviewPage)
          /_______________\
         /                 \
        /  Unit Tests       \  (Formatters, Components)
       /___________________\
```

### Phase Coverage (v2.0.2)
- ✅ Phase 1: Hard gates (security, IDOR, secrets, email validation)
- ✅ Phase 2: Data integrity (fee config boundaries, settlement safety)
- ✅ Phase 3: AI governance (budget atomicity, background task reliability)
- ✅ Phase 4: Frontend (component tests, integration tests, 60% coverage)

---

## API Documentation

### Generate OpenAPI Schema
```bash
# Backend serves OpenAPI at /openapi.json
curl http://localhost:8000/openapi.json | jq

# Frontend can generate TS types from it
cd frontend && npm run generate-types
```

### Key Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/v1/imports` | Bearer | Upload CSV/XLSX file (202 Accepted) |
| GET | `/v1/imports/{id}` | Bearer | Poll import status |
| GET | `/v1/insights/latest` | Bearer | Latest P&L snapshot |
| GET | `/v1/insights/history?weeks=4` | Bearer | Week-over-week history |
| POST | `/v1/insights/recompute` | Bearer | Re-run Rule Engine (Pro+ only) |
| GET | `/v1/actions` | Bearer | List all actions (pending + done) |
| PATCH | `/v1/actions/{id}/complete` | Bearer | Mark action as done |
| PATCH | `/v1/actions/{id}/dismiss` | Bearer | Dismiss action |
| GET | `/v1/shops/me` | Bearer | Current shop profile |
| PATCH | `/v1/shops/me` | Bearer | Update shop settings |
| POST | `/v1/cogs` | Bearer | Bulk upsert SKU cost-of-goods |

---

## License

**Proprietary** — Tikai is closed-source commercial software. All rights reserved.

---

## Support

- **Issues:** Report via internal issue tracker
- **Bugs:** Email support@tikai.vn
- **Feature requests:** Contact product@tikai.vn

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and breaking changes.

- **v2.0.2:** Add per-IP rate limiting, fix PII camelCase bypass, staging env validators
- **v2.0.1:** Fix Shopee platform field, add transaction_fee + order_processing_fee to orders
- **v2.0.0:** Initial production release

---

**Last updated:** May 2026 | **Audited:** Phase 1–4 production-readiness ✅
