# Cycle 10 - Performance and Capacity

## Load Profile

| Profile | Input | Expected behavior | Exit check |
| --- | --- | --- | --- |
| 10k rows | Weekly CSV/XLSX order export under 50 MB | Upload accepted, header detection offloaded, worker finishes within `job_timeout=300s` | Import status completes without API p95 breach |
| 30k rows | Multi-week export under 50 MB | Upload accepted, but operator guidance recommends weekly split if timeout risk appears | No API worker event-loop blocking during detection |

## Capacity Budget

- API DB pool: `pool_size=5`, `max_overflow=10`.
- Worker DB pool: `pool_size=5`, `max_overflow=5`.
- Worker concurrency: `max_jobs=10`, `job_timeout=300`, `max_tries=2`.
- With one Railway API and one worker process, worst-case DB connections are 25. With two API replicas, worst-case is 40.
- Supabase free tier should use PgBouncer/session limits carefully; Pro tier has more headroom.

## Hot Paths

- Upload API reads chunks into a linear `bytearray`, then converts once to `bytes`.
- XLSX header detection uses `asyncio.to_thread` so uvicorn workers are not blocked by openpyxl.
- COGS lookup has `ix_orders_shop_id_sku_name`.
- Import retry idempotency has `uq_orders_shop_tiktok_id`.

## Operator Checks

- Watch p95 import upload latency and API p95 latency separately.
- Alert if import duration p95 exceeds 240 seconds for 10k rows.
- For 30k rows, validate memory in staging before enabling larger seller cohorts.
- Scale worker before API if queue wait grows but API latency remains healthy.
