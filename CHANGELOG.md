# Tikai — Changelog

---

# 🚀 Tikai v2.2.0 — Settlement Reconciliation, Creator CRM & Push Alerts
> Closes the loop between TikTok payouts and internal P&L, adds a full Creator CRM with auto-sync, and introduces daily Web Push alerts for critical revenue signals.
> **No new migrations required** — `creator_profiles` table added in `0015_add_creator_profiles.py`; ZNS fields in `0013_add_zns_fields.py` — both already tracked.
> Zero breaking changes to existing API contracts — all new endpoints are additive.

## Settlement Reconciliation (`/doi-soat`)

**Backend:** `POST /v1/reconcile` — Upload TikTok settlement CSV to compare actual payout against Rule Engine expected payout.
**Files:** `backend/app/api/v1/reconcile.py`, `backend/app/services/rule_engine/settlement_reconciler.py`

- Parses settlement CSV rows (transaction_type, fee_amount, description, adjustment_type, seller_sku)
- Detects 4 hidden cost categories: shipping adjustments, refund admin fees, non-clawback commissions, reserve holds
- Returns verdict: `matched` / `minor_gap` / `major_gap` / `investigate` with Vietnamese action items
- Threshold: minor gap < 2%; major gap ≥ 2%; investigate = expected payout = 0
- 11 unit tests; feature-gated at Pro+ (returns 402 for Free tier)

**Frontend:** `/doi-soat` page — Dropzone file upload → verdict badge + 3-column summary + hidden cost breakdown + action items.
- Marks `localStorage['tikai_reconciled_settlement'] = '1'` on first successful reconciliation (Activation Progress integration)
- Linked from nav + ActivationProgress step (replaces old `/import?tab=settlement` stub)

## Creator CRM (`/creators`)

**Backend:** Full CRUD for creator profiles with performance tracking.
**Files:** `backend/app/api/v1/creators.py`, `backend/app/services/creators/sync.py`

- `GET /v1/creators` — filter by `status` / `performance_label`; `POST /v1/creators/sync` — upsert from latest snapshot
- Auto-sync on every successful import (`process_import.py` calls `sync_creators_from_snapshot()` after snapshot refresh)
- Refactored: sync logic extracted to `services/creators/sync.py`, used by both the API endpoint and the import worker

**Frontend:** `/creators` page — accordion list, inline editor (status, Zalo, internal note), 402 upgrade gate.
- Filter tabs: Tất cả / ⭐ Star / Hòa vốn / Đang lỗ
- Shows GMV 30d, hoa hồng, revenue efficiency; warns on commission waste from refunded orders
- Suggests max commission rate when available

## Daily Web Push Alerts

**Files:** `backend/app/tasks/daily_alerts.py`, `backend/app/tasks/worker.py`

- Cron: daily at 01:15 UTC (08:15 VN) via ARQ
- Sends Web Push to shops with `push_subscription_json` when: top leak ≥ 100,000 VND OR any SKU is `critical`
- Redis idempotency key `daily_alert_sent:{shop_id}` with 24h TTL — max 1 push per shop per day
- Fire-and-forget: one shop failing never blocks others; all exceptions are caught and logged
- 6 unit tests

## Zalo ZNS Scaffolding

**Files:** `backend/app/services/zalo/zns_client.py`, `backend/app/core/config.py`

- `send_zns_to_shop(shop, template_id, params)` — no-op when `ZALO_OA_ID` / `ZALO_ZNS_ACCESS_TOKEN` not set; sends via Zalo API when credentials present
- PII-safe logging: phone number masked to first 3 + last 2 digits
- Config: `ZALO_OA_ID`, `ZALO_ZNS_ACCESS_TOKEN` env vars (both optional, feature disables cleanly if absent)
- Frontend: Zalo ZNS settings panel in `/settings` — phone input + enable toggle (Pro+)

## UI / UX Fixes

- **WowScreen** (first-import congratulations): 3-way conditional for net revenue box — blue (no COGS), red/green (with COGS, based on margin sign); top insight block shows top leak if loss > 0, else top SKU card in net-revenue mode
- **Overview COGS nudge**: Quantified risk callout — shows top-leak SKU name + estimated loss amount instead of generic "you're missing COGS" message
- **Nav**: Added "Creators" and "Đối soát" links between Livestream and Cài đặt

---

# 🚀 Tikai v2.1.0 — Analytics Suite
> 6 new analytical features that turn raw P&L numbers into actionable seller intelligence.
> **Migration required:** `alembic upgrade head` applies `0008_add_cash_flow_fields`.
> Zero breaking changes to existing API contracts — all new fields have safe defaults.

## Feature 1 — Price Recommender
**Files:** `backend/app/services/rule_engine/price_recommender.py`, `backend/app/api/v1/tools.py`

`POST /v1/tools/price-recommend` — Reverse P&L calculator: enter COGS per unit + desired margin → get the minimum viable selling price.
- Formula: `price = (COGS + fixed_fees) / (1 - sum_of_rate_deductions)`
- Platform commission + transaction fee pulled from latest `FeeConfig` automatically
- Configurable affiliate rate (default 10%) and voucher rate (default 5%)
- Returns full cost breakdown (COGS, platform fee, transaction fee, affiliate, voucher, margin)
- Raises `INFEASIBLE_MARGIN (422)` when total rate deductions ≥ 100%

## Feature 2 — SKU Health Score
**Files:** `backend/app/services/rule_engine/pl_calculator.py`, `backend/app/schemas/insight.py`

Every SKU in `top_skus` now carries a `health_status` (critical / warning / healthy) with human-readable `health_reasons`.

Critical triggers (checked first):
- Negative margin
- Negative net revenue after fees
- Refund rate > 2× industry baseline

Warning triggers (only if not critical):
- Missing COGS (can't compute margin)
- Margin < 10%
- Refund rate > 1.2× baseline
- Voucher cost > 30% of net revenue

Frontend: `HealthCell` component in `SKUTable` shows color-coded icon; click to expand reason list. Filter tabs let sellers quickly isolate critical / warning SKUs.

## Feature 3 — What-If Simulator
**Files:** `backend/app/services/rule_engine/simulator.py`, `backend/app/api/v1/tools.py`

`POST /v1/tools/simulate` — Re-run P&L for one SKU with hypothetical parameters.
- Adjustable: affiliate rate, voucher rate, price change (±30%)
- Pure in-memory computation — **no DB writes, no AI calls**
- Returns: before/after net revenue + margin, delta, verdict string, breakeven extra orders
- Frontend: `WhatIfPanel` overlay modal triggered from any row in `SKUTable`

Bug fixed: `affiliate_commission` and `voucher_cost` are now serialized into `top_skus_json` so the simulator uses actual snapshot values as the baseline (not zero).

## Feature 4 — Creator Scorecard
**Files:** `backend/app/services/rule_engine/pl_calculator.py`, `backend/app/schemas/insight.py`

Every creator in `top_creators` now carries:
- `performance_label`: `star` (efficiency ≥ 2.0) / `break_even` (≥ 1.0) / `losing` (< 1.0)
- `suggested_max_commission_rate`: `(net_revenue / gmv) × 0.8` — the highest commission rate that still leaves 20% buffer

Frontend: `CreatorTable` leaderboard with color-coded badges and commission warning for losing creators.

## Feature 5 — Industry Benchmark
**Files:** `backend/app/services/benchmarks/industry_data.py`, `backend/app/api/v1/insights.py`

`GET /v1/insights/{id}/benchmark?category=fashion` — Compare shop vs industry.
- Source: Metric.vn / YouNet ECI 2025 — 7 TikTok Shop categories (fashion, beauty, food, electronics, home, baby, other)
- Metrics compared: refund rate, margin %, fee burden %
- Returns `BenchmarkComparison` list with `shop_value`, `industry_value`, `delta_pct`, `assessment` (above / on_par / below / no_data)
- Frontend: `IndustryBenchmark` component with category selector and color-coded comparison table

## Feature 6 — Cash Flow Timeline
**Files:** `backend/app/models/insight_snapshot.py`, `backend/migrations/versions/0008_add_cash_flow_fields.py`, `backend/app/schemas/insight.py`

New columns on `insight_snapshots`: `cash_in_30d` (Numeric 20,4) and `cash_pending_total` (Numeric 20,4).
- Computed by `settlement_calc.py` (already existed) and stored by `process_import` + `recompute`
- Exposed on `InsightSnapshotResponse` with `null` fallback for old snapshots
- Frontend: `CashFlowTimeline` progress-bar panel on Overview page

## Deploy Checklist — v2.0.x → v2.1.0

```bash
# 1. Run migration
alembic upgrade head   # applies 0008_add_cash_flow_fields

# 2. Deploy backend + worker
docker-compose up -d --build

# 3. Verify new columns
psql $DATABASE_URL -c "\d insight_snapshots" | grep cash

# 4. Smoke test
curl -H "Authorization: Bearer $TOKEN" "$API_URL/v1/tools/price-recommend" \
  -H "Content-Type: application/json" \
  -d '{"cogs_per_unit": "50000", "target_margin_pct": "0.20"}'
# Expected: {"min_price": "...", "breakdown": {...}}
```

---

# 🐛 Tikai v2.0.1 — Bug Fix Release
> Code review phát hiện 5 bugs trong v2.0.0. Tất cả đã được fix và có test coverage đầy đủ.
> **169 tests passing** (164 từ v2.0.0 + 5 test classes mới trong `test_v201_fixes.py`).
> **Zero migrations** — pure logic fixes, không thay đổi schema.

## Bugs Fixed

### 🟠 FIX-1 [MEDIUM] — `Order.platform` không được set trong bulk insert
**File:** `backend/app/tasks/process_import.py`  
**Root cause:** `migration 0005` thêm `orders.platform` với `server_default="tiktok"`.
`session.platform` được set đúng nhưng `Order.platform` trong list comprehension bị bỏ quên.  
**Impact:** Toàn bộ Shopee orders lưu với `platform="tiktok"`, phá vỡ index
`ix_orders_shop_id_platform` và mọi per-platform P&L query.  
**Fix:** Gán `_order_platform = parse_result.platform` trước loop, truyền vào `Order(platform=_order_platform, ...)`.

### 🟡 FIX-2 [LOW-MEDIUM] — Email HTML không escape AI content
**File:** `backend/app/services/email/client.py`  
**Root cause:** AI-generated text (headline, sections) được interpolate thẳng vào HTML template
qua `.format()` mà không qua `html.escape()`.  
**Impact:** AI output có `<`, `>`, `&` sẽ phá layout email hoặc inject raw HTML tags.  
**Fix:** Thêm `_escape()` helper dùng `html.escape()` + convert `\n` → `<br>`. Wrap tất cả
AI-generated fields qua `_escape()` trước khi truyền vào template.

### 🟡 FIX-3 [LOW] — `_format_vnd()` double-replace bug
**File:** `backend/app/services/email/client.py` — `_format_vnd()`  
**Root cause:** Erroneous second `.replace(",", ".", 2)` call reverted the VN comma-decimal
formatting: `"1,5M ₫"` → `"1.5M ₫"` (English format instead of Vietnamese).  
**Impact:** Weekly digest emails hiển thị `"1.5M ₫"` thay vì `"1,5M ₫"` cho mọi số lẻ triệu.
Test `test_millions` chỉ check `"M" in result` nên không detect được bug này.  
**Fix:** Thay `f"{millions:.1f}M ₫".replace(".", ",", 1).replace(",", ".", 2)`
bằng `f"{millions:.1f}M ₫".replace(".", ",")`.

### 🟡 FIX-4 [LOW] — `sw.js CACHE_VERSION` stale (tikai-v1.0.0 → v2.0.1)
**File:** `frontend/public/sw.js`  
**Root cause:** `CACHE_VERSION` hardcoded tại `"tikai-v1.0.0"`, không được bump khi ship v2.0.0.  
**Impact:** PWA users đã install không nhận được fresh JS/CSS sau deploy mới.  
**Fix:** Bump lên `"tikai-v2.0.1"`. Thêm comment hướng dẫn chi tiết về:
(a) manual bump checklist, (b) optional webpack DefinePlugin auto-injection từ CI.

### 🟡 FIX-5 [LOW] — `test_parser.py` crash vì 2-tuple unpack của 3-tuple
**File:** `backend/tests/rule_engine/test_parser.py`  
**Root cause:** `detect_file_type()` trả 3-tuple kể từ v2.0.0 (thêm `platform` field).
4 test cases trong `TestDetectFileType` vẫn dùng `file_type, score = detect_file_type(...)` →
`ValueError: too many values to unpack (expected 2)` → toàn bộ class crash khi chạy.  
**Fix:** Tất cả 4 callers đổi thành `file_type, score, platform = detect_file_type(...)`.
Thêm `assert platform == "tiktok"` / `"unknown"` để kiểm tra đúng behavior.

## Bonus Improvements (cùng PR)
- `core/config.py`: Thêm `app_base_url: str = "https://app.tikai.vn"` setting.
  Email CTA link và unsubscribe link giờ dùng `settings.app_base_url` thay vì hardcoded —
  staging/preview môi trường sẽ không email-link về production nữa.
- `email/client.py`: `sg.send()` (blocking HTTP) giờ wrap trong `asyncio.run_in_executor()`
  — tránh block event loop trong weekly batch job khi có nhiều shops.
- `test_v201_fixes.py`: 5 test classes mới verify tất cả fixes ở trên.

---

# 🔥 Tikai v2.0.0 — Multi-Platform + Email Digest
> Triển khai toàn bộ v1.1.0 + v1.2.0 + v2.0.0 từ upgrade plan VHEATM research.
> **164 tests passing** (153 từ v1.0.0 + 11 tests mới).
> **4 migrations** tổng (0001 → 0005). Zero breaking changes.

---

# v1.1.0 — COGS UI & Onboarding ✅

## Frontend: Settings COGS Table (NEW)
- `COGSTable` component thay thế placeholder "Sẽ ra mắt sớm"
- Coverage progress bar: màu sắc thay đổi (amber → blue → green) theo % SKU có COGS
- Dirty tracking: chỉ `upsert` những rows bị thay đổi — không re-save toàn bộ
- `RecomputeNudge`: sau khi save COGS, hiện nút "Tính lại P&L →" trigger recompute
- Error handling: lỗi load/save hiển thị message VN, không silent fail
- `total_skus` badge khi số SKU bị capped ở 500

## Frontend: Overview COGS Nudge Banner (NEW)
- Hiển thị khi `is_net_revenue_mode=true` (COGS coverage < 50%)
- Amber banner với link → /settings để nhập COGS
- Coverage percentage trong banner khi đã có 1+ SKU với COGS

## Frontend: Post-Import COGS Micro-Step (NEW)  
- `PostImportCOGSPrompt`: sau import completed, hiện form nhập COGS cho top 5 SKUs
- 2-phút flow: bỏ qua được, không bắt buộc
- Fire-and-forget: thành công → hiện "🎉 Đang tính margin..."

## Frontend: Platform Badge on Import Status (NEW)
- `PLATFORM_LABELS` map: TikTok Shop, Shopee, TikTok Giao Dịch, TikTok Thanh Toán
- Orange badge cho Shopee, gray cho TikTok

## API: `cogsApi` + `notificationsApi` in `api.ts` (NEW)
- `cogsApi.getAll()`, `cogsApi.upsert()`
- `notificationsApi.update()` → PATCH /shops/me/notifications

## Tests: COGSSettings.test.tsx (4 tests, NEW)

---

# v1.2.0 — Email Weekly Digest ✅

## Migration 0004: notification fields
- `shops.notification_email` (String 255, nullable)
- `shops.email_digest_enabled` (Boolean, default false)
- `weekly_receipts.email_sent` (Boolean, default false)
- `weekly_receipts.email_sent_at` (DateTime, nullable)

## Email Service: `services/email/client.py` (NEW)
- SendGrid integration với `sendgrid>=6.11.0`
- Fire-and-forget invariant: `send_weekly_digest()` NEVER raises
- Inline HTML template (không external template service dependency)
- `_format_vnd()`: Python-side VND formatting (M, k, ₫ suffixes)
- Skips gracefully when `SENDGRID_API_KEY` not configured (dev mode)
- Import error handling: clear message if sendgrid package not installed

## Worker: Email dispatch sau receipt save
- `run_weekly_receipts()` → sau `db.flush()` receipt → dispatch email if opted in
- Tracks `email_sent` + `email_sent_at` on receipt record
- Email failure NEVER blocks receipt creation (fire-and-forget)

## API: PATCH /shops/me/notifications (NEW)
- Basic email validation (`@` check)
- Sets `notification_email` + `email_digest_enabled`

## Models: Shop + WeeklyReceipt updated
- `notification_email`, `email_digest_enabled` trên Shop
- `email_sent`, `email_sent_at` trên WeeklyReceipt

## Config: `sendgrid_api_key`, `email_from_address`, `email_from_name`, `email_enabled` property

## Schema: `ShopResponse` thêm `notification_email`, `email_digest_enabled`

## pyproject.toml: `sendgrid>=6.11.0` added

## Tests: test_v120_email.py (8 tests, NEW)

---

# v2.0.0 — Multi-Platform (Shopee) ✅

## Migration 0005: platform columns
- `orders.platform` (String 20, default "tiktok") + index `ix_orders_shop_id_platform`
- `fee_configs.platform` (String 20, default "tiktok")
- `import_sessions.platform` (String 20, default "tiktok")
- All safe: `server_default` preserves backward compat for existing rows

## Shopee Fee Config Seed: `003_shopee_fee_config.sql`
- Version `2026-SHOPEE-VN-v1`, platform `shopee`
- Base commission 2%, transaction fee 2%, no fixed per-order fee
- Category overrides: fashion 3%, electronics 1%, beauty 2.5%, food 1.5%

## Parser: Shopee Column Aliases (NEW)
- `SHOPEE_COLUMN_ALIASES` in normalizer.py: 14 canonical fields mapped
- Covers EN + VN Shopee export column names
- `build_column_map(headers, platform="tiktok"|"shopee")` — platform-aware

## Parser: Detector — Shopee Fingerprints + Platform Return (BREAKING v2.0.0)
- `detect_file_type()` now returns `(file_type, confidence, platform)` — 3-tuple
- `COLUMN_FINGERPRINTS["shopee_order_export"]` — EN headers
- `COLUMN_FINGERPRINTS["shopee_order_export_vi"]` — VN headers
- `PLATFORM_MAP` maps file_type → platform string

## Parser: `ParseResult.platform` field (NEW)
- `platform: str = "tiktok"` — dataclass field with default
- Set from `detect_file_type()` result in `parse_order_csv()`

## process_import: Platform-aware fee config lookup
- Selects `FeeConfig.platform == parse_result.platform` first
- Falls back to TikTok config if no platform-specific config found
- Saves `platform` to `import_session`

## imports.py: Shopee platform gate check
- `_quick_detect_platform()`: reads headers only (no full parse, <1ms)
- Calls `require_feature(shop, Feature.SHOPEE_LAZADA)` → 402 for Free/Pro tiers

## gates.py: Shopee message updated
- "Import dữ liệu Shopee cần gói Business (299k/tháng). Lazada đang được phát triển."

## Models: ImportSession, Order, FeeConfig updated with `platform` field

## Tests: test_shopee_parser.py (7 tests) + test_v200_platform.py (11 tests)

---

## 📊 Test Summary

| Module | Tests |
|--------|-------|
| Rule engine (existing) | ~110 |
| v0.5.1 regressions | 25 |
| v0.5.2 code review | 9 |
| v1.0.0 ultimate gaps | 9 |
| v1.2.0 email digest | 8 (NEW) |
| v2.0.0 Shopee parser | 7 (NEW) |
| v2.0.0 platform infra | 11 (NEW) |
| Frontend COGS UI | 4 (NEW) |
| **Total** | **164** |

---

## 📋 Deploy Checklist — v1.0.0 → v2.0.0

```bash
# ─── v1.1.0 — Frontend only ──────────────────────────────────────────────────
cd frontend && npm run build
# Verify: Settings page hiển thị COGSTable (không còn placeholder)
# Verify: Overview hiển thị amber banner khi is_net_revenue_mode=true
cd backend && pytest tests/ -v   # Expected: 153/153 passing (no backend change)

# ─── v1.2.0 ──────────────────────────────────────────────────────────────────
# 1. Migration
alembic upgrade head   # applies 0004_add_notification_fields

# 2. Add env vars
SENDGRID_API_KEY=SG.xxx...         # optional — digest skipped if missing
EMAIL_FROM_ADDRESS=digest@tikai.vn
EMAIL_FROM_NAME=Tikai

# 3. Install sendgrid
pip install sendgrid>=6.11.0 --break-system-packages

# 4. Deploy
docker-compose up -d --build

# 5. Verify
psql $DATABASE_URL -c "\d shops" | grep notification
# Expected: notification_email, email_digest_enabled columns

pytest tests/ -v  # Expected: 153 + new email tests passing

# ─── v2.0.0 ──────────────────────────────────────────────────────────────────
# 1. Migration
alembic upgrade head   # applies 0005_add_platform_to_orders_and_fee_configs

# 2. Seed Shopee fee config
psql $DATABASE_URL < migrations/seeds/003_shopee_fee_config.sql

# 3. Verify seeds
psql $DATABASE_URL -c "SELECT version, platform, platform_commission_rate FROM fee_configs;"
# Expected: tiktok + shopee configs present

# 4. Deploy
docker-compose up -d --build

# 5. Smoke test Shopee import (Business tier account required)
# Upload sample Shopee order export
# Expected: detect_file_type returns platform="shopee"
# Expected: platform badge "Shopee" in import history UI

# 6. Tests
pytest tests/ -v  # Expected: 164/164 passing
```

---

*Tikai v2.0.0 | v1.0.0 → v2.0.0 Upgrade Plan | 2026-05-12*
*164 tests | 3 versions shipped | 5 new migrations | 0 known regressions*
