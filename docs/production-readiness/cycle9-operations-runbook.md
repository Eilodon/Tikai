# Cycle 9 - Observability and Operations Runbook

## Signals

- Structured request logs emit `http.request` and `http.request_failed` with `request_id`, path, status, and `duration_ms`.
- Sentry is mandatory for staging/production through `SENTRY_DSN`.
- Business metrics to dashboard: import success/failure count, import duration, AI budget rejection count, action completion count, weekly receipt delivery failure count, daily alert send count, public calculator errors.

## Alert Thresholds

- p95 API latency > 1500 ms for 10 minutes.
- import failure rate > 5% over 30 minutes or 3 failures for one shop in 15 minutes.
- stuck worker: `pending` or `processing` import older than 30 minutes.
- bad fee config: startup log `startup.fee_config_missing` or sudden margin shifts after deploy.
- AI outage: AI call failure rate > 10% over 15 minutes or AI budget rejection spike > 20 per hour.
- email/push failure: weekly receipt delivery failure count > 0 after Monday digest window.

## Diagnose Failed Import

1. Search logs by `request_id`, `shop_id`, and `import_session_id`.
2. Inspect `import_sessions.status`, `error_summary`, `rows_parsed`, and `rows_failed`.
3. Check Supabase Storage path availability and `/readyz` storage status.
4. Replay parser locally with the same fixture class if the file is non-sensitive; otherwise use schema-only diagnostics.

## Diagnose Stuck Worker

1. Check Railway worker process health and ARQ Redis connectivity.
2. Query imports older than 30 minutes in `pending` or `processing`.
3. Confirm `cleanup_stuck_imports` logs and retry count.
4. Restart worker only after confirming no active job is still progressing.

## Diagnose Bad Fee Config

1. Check startup logs for `startup.fee_config_ok` by platform.
2. Verify `fee_configs` effective date and platform rows.
3. Recompute a known snapshot and compare fee version and margin deltas.
4. Roll back fee config migration or patch data, then rerun affected shop recomputes.

## Diagnose AI Outage

1. Check Sentry and logs for `ai.call_failed`, `ai.budget_reservation_*`, and provider status.
2. Confirm model names from `ai.models_active` startup log.
3. Validate Redis budget keys for the affected shop and month.
4. Use deterministic fallback templates for user-facing copy until provider recovers.

## Diagnose Email/Push Failure

1. Check SendGrid/Zalo/Web Push credentials in Railway variables.
2. Confirm shop notification opt-in fields and weekly receipt `email_sent` state.
3. Inspect provider response logs without exposing recipient PII.
4. Retry only idempotent receipt sends; never duplicate receipts for the same shop/week.

## Backup and Restore

- Backup: daily Supabase/Postgres snapshot, plus export of migration version and fee config rows.
- Restore drill: monthly restore into staging, run `alembic current`, `/readyz`, import smoke, overview smoke, and one worker receipt job.
- Recovery point objective: 24 hours for database state; uploaded import files are recoverable through Supabase Storage lifecycle backups.
