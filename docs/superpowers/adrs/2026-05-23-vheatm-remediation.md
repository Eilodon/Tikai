# ADR: VHEATM Tier 3 Remediation - Async State & DB Isolation

## 1. Title
Implementation of SAVEPOINT and Pessimistic Locking to resolve Tainted Session and Lost Update vulnerabilities.

## 2. Context
During the VHEATM Tier-3 Audit, three critical vulnerabilities were identified:
1. `Tainted Session` in `process_import.py`: A `try...except` block caught an exception from a DB insert inside an `AsyncSession`, but the session state transitioned to `PendingRollbackError`. The outer transaction continued, causing the entire async import process to crash when `commit()` was invoked.
2. `Lost Update / Write Skew` in `inventory.py` and `cogs.py`: Concurrent mutations to the JSONB columns `stock_map` and `cogs_map` resulted in data overwrites because they used standard Read-Modify-Write patterns under Read Committed isolation, lacking Row Locks.
3. `Silent Failure / Null Dereference`: Pydantic input models for AI calls were instantiated outside `try...except` blocks, risking task-crashing `ValidationError`s.

## 3. Decision
- **Tainted Session:** We wrapped the non-critical database operation (`sync_creators_from_snapshot`) in an `async with db.begin_nested():` block. This leverages PostgreSQL `SAVEPOINT`, ensuring that inner exceptions do not taint the outer transaction.
- **Lost Update:** We implemented Pessimistic Locking by applying `.with_for_update()` to `select(Shop)` statements before any JSONB dictionary mutation in `cogs.py` and `inventory.py`.
- **Silent Failures:** We moved Pydantic `AhaNarrativeInput` and `ActionCoachInput` instantiations inside the `try...except` block in `process_import.py`.

## 4. Status
ACCEPTED

## 5. Consequences
- **Improved:** Import stability guarantees are upheld. Concurrent updates by multiple admins will securely serialize via DB row locks. AI logic degrades gracefully on malformed DB state.
- **Worsened:** Slight latency increase on concurrent API requests hitting `inventory.py` and `cogs.py` due to row-level locks waiting for transactions to complete.
- **Debt Created:** Pydantic validation failures will now be silently suppressed inside the AI loops. A dead-letter queue or dedicated error telemetry might be needed later.

## 6. Alternatives Considered
- *JSONB SQL Operations:* For the Lost Update, we considered using PostgreSQL native `jsonb_set` instead of Pessimistic Locking. *Rejected* because SQLAlchemy's mapping of JSONB is simpler to maintain via Dict mutation and flag_modified, and locking `Shop` provides atomic safety for all columns during the transaction.

## 7. Evidence
- Source code in `cogs.py`, `inventory.py` and `process_import.py` manually verified against these principles.

## 8. Owner
Eidolon-V (Operator)

## 8b. Known Debts (PATTERN-DEBT)
None newly introduced.

## 9. Next Cycle Trigger
When Shop entity mutations start taking >200ms on P95 latency (due to lock contention), we will re-evaluate JSONB column updates vs native SQL `jsonb_set` operations.

## 10. Cycle Retrospective
- What assumption proved wrong during this implementation? The assumption that `try...except` in Python prevents SQLAlchemy transactions from failing.
- What surprised us about the codebase / domain / dependencies? The system used Pydantic validation prior to AI tasks but placed them outside safety blocks.
- What would we design differently if starting over? Isolate AI inputs mapping into strict mapping layers before pushing to background workers.
- What debt was knowingly created and why? Pessimistic lock contention on the Shop table during COGS updates.
- What signal should the next cycle watch for? Watch for `PendingRollbackError` in any background workers that share `AsyncSession`.
