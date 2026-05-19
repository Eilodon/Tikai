# First Deploy Runbook

Step-by-step guide for the **very first production deployment** of Tikai.
Covers Railway (backend + worker) + Vercel (frontend) + Supabase (auth + storage).

## Prerequisites

- Railway account with a project created
- Vercel account with team workspace
- Supabase project provisioned (PostgreSQL 16, Auth enabled, Storage bucket "imports" created)
- Anthropic API key with production spending limit set
- SendGrid account (optional — email digest disabled if not set)

---

## Step 1: Provision Supabase

1. Create Supabase project → note `Project URL`, `anon key`, `service_role key`, `JWT Secret`.
2. In Supabase Storage → create bucket `imports` (private, no public access).
3. In Supabase Auth → enable Email provider, set `Site URL` to `https://app.tikai.vn`.
4. In Supabase Auth → enable redirect URLs: `https://app.tikai.vn/auth/callback`.

---

## Step 2: Deploy Backend to Railway

### 2a. Set environment variables in Railway

```
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>?sslmode=require
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>
ANTHROPIC_API_KEY=<anthropic-key>
REDIS_URL=redis://<host>:6379
ALLOWED_ORIGINS=["https://app.tikai.vn"]
SENTRY_DSN=<sentry-dsn>
APP_BASE_URL=https://app.tikai.vn
SENDGRID_API_KEY=<sendgrid-key>
ADMIN_SECRET=<random-32-char-string>

# Optional — push notifications
VAPID_PRIVATE_KEY=<generated>
VAPID_PUBLIC_KEY=<generated>

# Optional — Zalo ZNS (pending Zalo Business approval)
# ZALO_OA_ID=
# ZALO_ZNS_ACCESS_TOKEN=
```

**Validate before deploying:** All required vars must be present. Missing `SENTRY_DSN` or `DATABASE_URL` without SSL will cause startup failure (fail-fast validators in `config.py`).

### 2b. Deploy API service

```bash
# Railway will auto-detect railway.json and use Dockerfile.prod
railway up --service api
```

### 2c. Run database migrations

Connect to the Railway shell or run via Railway CLI:
```bash
railway run alembic upgrade head
```

### 2d. Seed fee_config data

The app will CRITICAL-log on startup if fee configs are missing. Seed them:
```bash
railway run python migrations/seeds/seed_fee_configs.py
```

Verify via startup log: look for `startup.fee_config_ok` for platforms `tiktok`, `shopee`, `lazada`.

### 2e. Deploy Worker service

```bash
railway up --service worker
```

The worker uses the same env vars as the API. Verify it starts with no ARQ errors.

---

## Step 3: Verify Backend Health

```bash
# Liveness — must return {"status": "ok", "version": "2.3.0"}
curl https://<api-railway-url>/healthz

# Readiness — must return {"status": "ready", "db": "ok", "redis": "ok", "storage": "ok"}
curl https://<api-railway-url>/readyz
```

If `/readyz` returns errors:
- `db`: Check DATABASE_URL SSL, connection limit, Supabase project active
- `redis`: Check REDIS_URL, Railway Redis service running
- `storage`: Check SUPABASE_SERVICE_ROLE_KEY, bucket "imports" exists

---

## Step 4: Deploy Frontend to Vercel

### 4a. Set environment variables in Vercel

```
NEXT_PUBLIC_API_URL=https://<api-railway-url>
NEXT_PUBLIC_SUPABASE_URL=https://<project-id>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

### 4b. Deploy

```bash
vercel --prod
```

---

## Step 5: Smoke Tests (must pass before opening traffic)

Run these manually or automate as a post-deploy step:

| Test | Expected Result |
|------|----------------|
| Visit `https://app.tikai.vn/login` | Login page loads |
| Sign up with test account | Redirected to `/overview` |
| `/overview` shows empty state with import CTA | No crash, no raw errors |
| Upload a TikTok Shop CSV | Import session created, status eventually `completed` |
| Check `/overview` after import | P&L data displays with correct VND formatting |
| Visit `/tinh-gia-ban` (public tool) | Price calculator renders without auth |
| Verify Sentry receives one test event | Go to Sentry dashboard, trigger `POST /v1/imports` with bad file |

---

## Step 6: Verify Monitoring

1. **Sentry**: Confirm the project receives events. Test by uploading an invalid file.
2. **Railway metrics**: Check CPU, memory, and response time after smoke tests.
3. **Startup logs**: In Railway logs, confirm `startup.fee_config_ok` for all 3 platforms.

---

## Step 7: Open Traffic

1. Set Vercel project domain to `app.tikai.vn` (DNS CNAME → cname.vercel-dns.com).
2. Remove any "coming soon" page or maintenance mode.
3. Monitor Railway logs for the first 30 minutes.
4. Alert threshold: if `import failure rate > 5%` in first hour, pause and investigate.

---

## Rollback

If production is broken after deploy:

1. In Vercel: go to Deployments → redeploy previous version.
2. In Railway: redeploy previous image from deployment history.
3. If a migration caused the issue: do NOT run `alembic downgrade` in production without a data backup. Restore from Supabase snapshot instead.
4. Verify `/readyz` returns `ready` after rollback.
