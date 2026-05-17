"""Cycle 8 deployment/runtime readiness checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readyz_covers_real_runtime_dependencies():
    main_source = (ROOT / "backend/app/main.py").read_text()
    storage_source = (ROOT / "backend/app/core/storage.py").read_text()

    assert 'errors["db"]' in main_source
    assert 'errors["redis"]' in main_source
    assert 'errors["storage"]' in main_source
    assert "check_storage_ready" in storage_source
    assert "/storage/v1/bucket/" in storage_source


def test_docker_prod_respects_runtime_port_and_healthcheck():
    dockerfile = (ROOT / "backend/Dockerfile.prod").read_text()

    assert "${PORT:-8000}" in dockerfile
    assert 'os.getenv("PORT", "8000")' in dockerfile
    assert "/healthz" in dockerfile


def test_railway_api_and_worker_configs_match_repo_commands():
    api = (ROOT / "backend/railway.json").read_text()
    worker = (ROOT / "backend/railway.worker.json").read_text()

    assert "Dockerfile.prod" in api
    assert '"healthcheckPath": "/readyz"' in api
    assert "uvicorn app.main:app" in api
    assert "python -m arq app.tasks.worker.WorkerSettings" in worker


def test_vercel_config_requires_frontend_backend_and_supabase_envs():
    vercel = (ROOT / "frontend/vercel.json").read_text()

    assert "NEXT_PUBLIC_API_URL" in vercel
    assert "NEXT_PUBLIC_SUPABASE_URL" in vercel
    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in vercel
