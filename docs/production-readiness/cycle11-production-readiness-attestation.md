# Cycle 11 - Production Readiness Attestation

## Status

Production readiness is conditionally signed for staging rollout after the gates below pass on the target branch and environment.

- No open CRITICAL findings.
- No open MANDATORY findings.
- Cycle 4 worker resilience guards added.
- Cycle 5 AI safety and budget race guards added.
- Cycle 6 security/compliance findings mapped and patched.
- Cycle 7 Playwright smoke suite added for login, import, overview, actions, settings, and public tools.
- Cycle 8 deploy/readiness checks aligned with Railway, Vercel, Docker, DB, Redis, and Storage.
- Cycle 9 operations runbook covers failed import, stuck worker, bad fee config, AI outage, email/push failure, backup, and restore.
- Cycle 10 capacity profile covers 10k rows and 30k rows.
- Cycle 11 final gate requires CI/security/build/e2e rerun before production traffic.

## Attestation Expiry

This attestation expires 7 days after the latest successful final gate run, or immediately after any migration, auth, import parser, worker, AI, billing, deployment, or secrets change.

## Rollback Plan

1. Disable new traffic at Vercel or point frontend to previous Railway API URL.
2. Redeploy previous Railway API and worker image.
3. Verify `/healthz`, `/readyz`, and one authenticated overview request.
4. If a migration caused the incident, restore from the latest Supabase/Postgres snapshot into staging first, validate data shape, then apply the documented downgrade or data repair.
5. Re-run import smoke and worker receipt smoke before reopening traffic.

## Launch Checklist

- Backend `pytest` pass.
- Backend `ruff check` and `ruff format --check` pass.
- Frontend `npm run type-check`, `npm run lint`, `npm test`, `npm run build`, and `npm run test:e2e` pass.
- `npm audit --audit-level=high` pass or has documented accepted risk.
- `pip check` pass.
- Staging env variables match `docs/production-readiness/cycle8-deployment-runtime.md`.
- `/readyz` returns DB, Redis, and Storage as `ok`.
- Sentry project receives one staging test event.
- Operator has runbook access before launch.
