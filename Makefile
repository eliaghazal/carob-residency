# Carob: common tasks. `make help` lists them.
SHELL := /bin/bash
TEST_DB ?= postgresql+psycopg://carob:carob@localhost:5432/carob_test
RESIDENCY_KIT ?= ../carob-residency-acceptance
RELEASE := docker compose --project-directory . -f infra/compose.release.yaml

.PHONY: help dev down logs test lint format typecheck migrate seed web-dev web-test observe \
        staging-up staging-down prod-up prod-down traffic data train evaluate drill drill-check

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

dev: ## run the whole stack locally with hot reload
	docker compose up --build

down: ## stop the dev stack (data is kept)
	docker compose down

logs: ## follow the API and worker logs
	docker compose logs -f api worker

test: ## run the Python tests against the dev Postgres (carob_test database)
	docker compose up -d --wait db
	CAROB_DATABASE_URL=$(TEST_DB) uv run pytest

lint: ## ruff
	uv run ruff check . && uv run ruff format --check .

format: ## format the Python code
	uv run ruff format . && uv run ruff check --fix .

typecheck: ## mypy and tsc
	uv run mypy
	cd web && npm run typecheck

migrate: ## apply migrations to the dev database
	docker compose run --rm migrate alembic upgrade head

seed: ## reference data and demo customers
	docker compose run --rm migrate python -m carob.seed --demo

web-dev: ## the staff console on http://localhost:5173 (needs the API running)
	cd web && npm install && npm run dev

web-test: ## console tests
	cd web && npm test

observe: ## Prometheus and Grafana for the dev stack
	docker compose --profile observability up -d prometheus grafana

staging-up: ## run the staging release (images tagged staging)
	$(RELEASE) -p carob-staging --env-file infra/env/staging.env pull
	$(RELEASE) -p carob-staging --env-file infra/env/staging.env up -d --wait

staging-down:
	$(RELEASE) -p carob-staging --env-file infra/env/staging.env down

prod-up: ## run the production release (images tagged production)
	$(RELEASE) -p carob-prod --env-file infra/env/production.env pull
	$(RELEASE) -p carob-prod --env-file infra/env/production.env up -d --wait

prod-down:
	$(RELEASE) -p carob-prod --env-file infra/env/production.env down

traffic: ## simulated customers against production (BASE=... to change)
	uv run python scripts/traffic.py --base $${BASE:-http://localhost:8200} --paystub $${PAYSTUB:-http://localhost:8290}

data: ## build the routing dataset from Hugging Face and GitHub
	uv run --group ml python -m carob_ml data

train: ## train the support router into models/router/
	uv run --group ml python -m carob_ml train

evaluate: ## evaluate the newest router by language variety
	uv run --group ml python -m carob_ml evaluate

drill: ## start an incident drill (Dojo gives you the CODE)
	@test -n "$(CODE)" || (echo "usage: make drill CODE=<code from Dojo>"; exit 2)
	uv run python $(RESIDENCY_KIT)/drills/run.py start $(CODE)

drill-check: ## check whether the drill's incident is mitigated
	uv run python $(RESIDENCY_KIT)/drills/run.py check
