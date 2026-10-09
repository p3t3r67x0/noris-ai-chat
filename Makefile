COMPOSE ?= sh infrastructure/scripts/compose.sh

.PHONY: install dev backend-dev db-up db-diagnose network-repair dev-up generate-api check-api lint typecheck test test-unit test-integration test-llm-integration test-e2e build up down migrate python-typecheck

install:
	uv sync --project backend --locked
	pnpm install --frozen-lockfile

dev:
	pnpm dev

backend-dev:
	uv run --directory backend --locked uvicorn noris_ai.main:app --reload --host 127.0.0.1 --port 8000

db-up:
	$(COMPOSE) -f compose.yaml -f compose.dev.yaml up -d --wait postgres

db-diagnose:
	$(COMPOSE) run --rm --no-deps -T migrate python - < backend/scripts/check_database.py

network-repair:
	sh infrastructure/scripts/repair-docker-network.sh

dev-up:
	$(COMPOSE) -f compose.yaml -f compose.dev.yaml up --build --wait

generate-api:
	pnpm api:generate

check-api:
	pnpm api:check

lint:
	uv run --project backend --locked ruff check backend
	uv run --project backend --locked ruff format --check backend
	pnpm lint

python-typecheck:
	uv tool run --from pyright==1.1.408 pyright --project backend/pyproject.toml

typecheck: python-typecheck
	pnpm typecheck
	pnpm typecheck:tools

test: test-unit test-integration test-e2e

test-unit:
	uv run --project backend --locked pytest backend/tests/unit backend/tests/contract backend/tests/llm_integration
	pnpm test

test-llm-integration:
	uv run --project backend --locked pytest backend/tests/llm_integration

test-integration:
	uv run --project backend --locked pytest backend/tests/integration

test-e2e:
	pnpm test:e2e
	pnpm --dir frontend test:e2e:llm

build:
	uv build --project backend
	pnpm build

up:
	$(COMPOSE) up --build --wait

down:
	$(COMPOSE) down

migrate:
	uv run --directory backend --locked alembic upgrade head
