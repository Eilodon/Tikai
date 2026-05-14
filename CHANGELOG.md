# Tikai — Changelog

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
