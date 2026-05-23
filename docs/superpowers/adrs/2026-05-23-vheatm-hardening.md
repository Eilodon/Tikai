# ADR: VHEATM Tier 3 Hardening - Worker Thread Pool, Unified Sentry, and Next.js Middleware Protection

## 1. Title
Decoupling Sentry telemetry, transitioning CSV parser to thread pool (blocking I/O), and locking E2E auth bypass in Next.js Middleware.

## 2. Context
During the VHEATM Tier-3 Audit, three critical operational issues were identified:
1. **Blocking CSV Parsing:** The ARQ worker processed large order CSVs synchronously using Pandas in `app/tasks/process_import.py`. This blocked the single-threaded Python event loop, starving other tasks and causing worker timeout/connection drops under load.
2. **Scattered Sentry Initialization:** Sentry SDK was initialized in `app/main.py` but missing in `app/tasks/worker.py` (ARQ background runner). This left background worker exceptions unmonitored.
3. **E2E Auth Bypass Leak:** Frontend `middleware.ts` allowed bypassing registration logic if `process.env.E2E_AUTH_BYPASS === "true"`, without checking if the app was running in production mode (`process.env.NODE_ENV === "production"`).

## 3. Decision
- **Thread Pool Offloading:** Wrapped `parse_order_csv` in `await asyncio.to_thread(...)` inside `app/tasks/process_import.py`. This schedules the CPU-bound csv parsing in a separate system thread.
- **Unified Telemetry:** Created a core telemetry module `app/core/sentry.py` with `init_sentry(is_worker)`. Integrated it into `app/main.py` (FastAPI app) and `app/tasks/worker.py` (ARQ startup). The arq worker dynamically loads `ArqIntegration` to avoid imports failure on non-worker setups.
- **Middleware Hardening:** Modified Next.js `middleware.ts` to strictly prohibit `E2E_AUTH_BYPASS` in production environments: `process.env.E2E_AUTH_BYPASS === "true" && process.env.NODE_ENV !== "production"`.

## 4. Status
ACCEPTED

## 5. Consequences
- **Improved:**
  - Background worker event loops are non-blocking. P95 worker task processing latency is isolated from sync parsing delays.
  - Complete error observability across both FastAPI web server and ARQ worker.
  - Zero risk of E2E Auth Bypass vulnerability leaking into production deployments.
- **Worsened:**
  - Slight context switching overhead due to OS threads spawning for `asyncio.to_thread`.
- **Debt Created:**
  - None.

## 6. Alternatives Considered
- *ProcessPoolExecutor:* Considered running CSV parsing in a separate Python process. *Rejected* because `to_thread` provides sufficient performance without process serialization overhead, as the worker runs on a multi-core server and GIL is released during pandas C-level execution.

## 7. Evidence
- Source code in `process_import.py`, `worker.py`, `main.py`, and `middleware.ts` modified.
- Full unit test suite `tests/test_vheatm_hardening.py` created and verified green.
- Next.js type-checking and production build verified green.

## 8. Owner
Eidolon-V (Operator)
