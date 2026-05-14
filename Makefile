.PHONY: up down backend frontend migrate seed test lint typecheck

# ── Local Dev ──────────────────────────────────────────────────────────────────

up:
	docker-compose up -d
	@echo "✓ PostgreSQL + Redis running"

down:
	docker-compose down

# ── Backend ────────────────────────────────────────────────────────────────────

install-backend:
	cd backend && pip install -e ".[dev]"

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && python -m arq app.tasks.worker.WorkerSettings

migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(name)"

seed:
	cd backend && python scripts/seed_fee_config.py

# ── Frontend ───────────────────────────────────────────────────────────────────

install-frontend:
	cd frontend && npm install

frontend:
	cd frontend && npm run dev

generate-types:
	cd frontend && npm run generate-types

# ── Quality ────────────────────────────────────────────────────────────────────

test:
	cd backend && pytest tests/rule_engine/ -v --tb=short

test-ai:
	cd backend && pytest tests/ai/ -m ai_eval -v --tb=short

lint:
	cd backend && ruff check app/ tests/
	cd frontend && npm run lint

format:
	cd backend && ruff format app/ tests/

typecheck:
	cd backend && mypy app/
	cd frontend && npm run type-check

# ── Full setup ─────────────────────────────────────────────────────────────────

setup: up install-backend install-frontend migrate seed
	@echo "✓ Tikai dev environment ready"
	@echo "  Backend:  http://localhost:8000/docs"
	@echo "  Frontend: http://localhost:3000"
