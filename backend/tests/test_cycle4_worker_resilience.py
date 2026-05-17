"""
Cycle 4 resilience guards: worker cron, idempotency, Redis/DB chaos, and ARQ retry safety.
"""

import inspect

import pytest


class BrokenRedis:
    async def get(self, key: str):
        raise ConnectionError("redis down")

    async def set(self, key: str, value: str, ex: int):
        raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_daily_alert_redis_down_fails_open_for_dedup():
    from app.tasks.daily_alerts import _mark_shop_alerted, _shop_was_alerted_today

    redis = BrokenRedis()

    assert await _shop_was_alerted_today("shop-1", redis) is False
    await _mark_shop_alerted("shop-1", redis)


@pytest.mark.asyncio
async def test_weekly_receipt_trigger_db_down_bubbles_to_arq_retry():
    from app.tasks.worker import WorkerSettings, trigger_weekly_receipts

    class BrokenSession:
        async def __aenter__(self):
            raise ConnectionError("db down")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class BrokenSessionFactory:
        def __call__(self):
            return BrokenSession()

    assert WorkerSettings.max_tries >= 2

    with pytest.raises(ConnectionError, match="db down"):
        await trigger_weekly_receipts({"db_session_factory": BrokenSessionFactory(), "arq": None})


def test_weekly_receipt_duplicate_jobs_have_queue_and_db_idempotency():
    from app.models.weekly_receipt import WeeklyReceipt
    from app.tasks import worker

    trigger_source = inspect.getsource(worker.trigger_weekly_receipts)
    job_source = inspect.getsource(worker.process_weekly_receipt_for_shop)

    assert "_job_id=job_id" in trigger_source
    assert "weekly-receipt-{shop_id}-{week_label}" in trigger_source
    assert "WeeklyReceipt.period_label == week_label" in job_source
    constraints = [
        item for item in WeeklyReceipt.__table_args__ if getattr(item, "name", None) is not None
    ]
    assert any(item.name == "uq_weekly_receipts_shop_period" for item in constraints)


def test_process_import_sigkill_retry_skips_terminal_sessions():
    from app.tasks import process_import as process_import_module

    source = inspect.getsource(process_import_module.process_import)

    assert 'session.status in {"completed", "completed_with_caveats"}' in source
    assert "InsightSnapshot.import_session_id == session.id" in source
    assert "process_import.idempotent_terminal_skip" in source
    assert "return" in source[source.find("process_import.idempotent_terminal_skip") :]


def test_worker_timeout_and_retry_budget_are_explicit():
    from app.tasks.worker import WorkerSettings

    assert WorkerSettings.job_timeout == 300
    assert WorkerSettings.max_tries >= 2
    assert WorkerSettings.keep_result >= 3600
