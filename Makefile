.PHONY: install dev backend frontend test lint

install:  ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

dev:  ## Run backend (port 8000) and frontend (port 5173) together
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:  ## Run backend tests
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint
