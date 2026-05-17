# Cycle 8 - Deployment and Runtime Readiness

## Staging Deploy Checklist

- Railway API uses `backend/Dockerfile.prod`, starts `uvicorn app.main:app`, and checks `/readyz`.
- Railway worker uses the same image and starts `python -m arq app.tasks.worker.WorkerSettings`.
- Vercel must set `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- Backend staging/prod must set `ENVIRONMENT`, `DATABASE_URL` with SSL, `REDIS_URL`, Supabase service role/JWT secrets, `ANTHROPIC_API_KEY`, `SENTRY_DSN`, and strict `ALLOWED_ORIGINS`.
- Run `alembic upgrade head` before routing user traffic to a new backend image.
- `/readyz` must return DB, Redis, and Storage as `ok`; `/healthz` only proves process liveness.
- Roll back by redeploying the previous Railway API and worker image, then verifying `/readyz` and one import smoke.

## Repo Reality

- API config: `backend/railway.json`
- Worker config: `backend/railway.worker.json`
- Docker image: `backend/Dockerfile.prod`
- Frontend config: `frontend/vercel.json`
- Readiness code: `backend/app/main.py`
