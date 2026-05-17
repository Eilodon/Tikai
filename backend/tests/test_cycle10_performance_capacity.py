"""Cycle 10 performance and capacity guardrails."""

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_import_upload_uses_linear_buffer_and_threaded_xlsx_detection():
    from app.api.v1 import imports

    source = inspect.getsource(imports.upload_import)

    assert "bytearray()" in source
    assert ".extend(chunk)" in source
    assert "file_bytes += chunk" not in source
    assert "asyncio.to_thread(_quick_detect_platform" in source
    assert "MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024" in inspect.getsource(imports)


def test_orders_have_capacity_indexes_for_shop_sku_and_idempotency():
    sku_index = (ROOT / "backend/migrations/versions/0007_add_orders_sku_name_index.py").read_text()
    unique_order = (
        ROOT / "backend/migrations/versions/0016_add_order_unique_constraint.py"
    ).read_text()

    assert "ix_orders_shop_id_sku_name" in sku_index
    assert '["shop_id", "sku_name"]' in sku_index
    assert "uq_orders_shop_tiktok_id" in unique_order
    assert '["shop_id", "tiktok_order_id"]' in unique_order


def test_worker_and_db_connection_budget_is_explicit():
    worker = (ROOT / "backend/app/tasks/worker.py").read_text()
    database = (ROOT / "backend/app/core/database.py").read_text()
    profile = (ROOT / "docs/production-readiness/cycle10-performance-capacity.md").read_text()

    assert "max_jobs = 10" in worker
    assert "job_timeout = 300" in worker
    assert "pool_size=5" in worker
    assert "max_overflow=5" in worker
    assert "pool_size=5" in database
    assert "max_overflow=10" in database
    assert "10k rows" in profile
    assert "30k rows" in profile
