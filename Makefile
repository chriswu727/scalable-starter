# =============================================================================
# Scalable Starter — one entrypoint for every common task.
# Run `make help` to see everything. Designed so a new contributor can go from
# `git clone` to a running stack with two commands: `make setup` then `make up`.
# =============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------- Setup ----------
.PHONY: setup
setup: ## Install all dependencies (JS + Python) and copy env
	@test -f .env || cp .env.example .env
	corepack enable && pnpm install --frozen-lockfile
	cd apps/api && python -m venv .venv && . .venv/bin/activate \
		&& pip install -r requirements-dev.txt && pip install --no-deps -e .
	@echo "Setup complete. Run 'make up' to start the stack."

.PHONY: lock
lock: ## Regenerate dependency lockfiles (pnpm + Python) after changing manifests
	pnpm install --lockfile-only
	cd apps/api && uv pip compile pyproject.toml --universal -o requirements.txt
	cd apps/api && uv pip compile pyproject.toml --universal --all-extras -o requirements-dev.txt

# ---------- Local stack (Docker) ----------
.PHONY: up
up: ## Start the full stack (web, api, postgres, redis) via docker compose
	$(COMPOSE) up --build

.PHONY: up-d
up-d: ## Start the stack in the background
	$(COMPOSE) up --build -d

.PHONY: down
down: ## Stop the stack and remove containers
	$(COMPOSE) down

.PHONY: clean-volumes
clean-volumes: ## Stop the stack and DELETE data volumes (destructive)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

# ---------- Dev (no containers) ----------
.PHONY: dev
dev: ## Run web + api in watch mode locally (requires `make setup`)
	turbo run dev

# ---------- Database ----------
.PHONY: migrate
migrate: ## Apply all database migrations
	cd apps/api && . .venv/bin/activate && alembic upgrade head

.PHONY: migration
migration: ## Create a new migration: make migration m="add users"
	cd apps/api && . .venv/bin/activate && alembic revision --autogenerate -m "$(m)"

# ---------- Quality gates ----------
.PHONY: lint
lint: ## Lint everything (JS + Python)
	pnpm lint
	pnpm format:check
	cd apps/api && . .venv/bin/activate && ruff check . && ruff format --check .

.PHONY: format
format: ## Auto-format everything
	pnpm format
	cd apps/api && . .venv/bin/activate && ruff format . && ruff check --fix .

.PHONY: typecheck
typecheck: ## Static type checks (tsc + mypy)
	pnpm typecheck
	cd apps/api && . .venv/bin/activate && mypy app

.PHONY: test
test: ## Run all tests
	pnpm test
	cd apps/api && . .venv/bin/activate && pytest

.PHONY: cov
cov: ## API test coverage report (CI enforces --cov-fail-under=70)
	cd apps/api && . .venv/bin/activate && pytest --cov=app --cov-report=term-missing

.PHONY: check
check: lint typecheck test ## Run the full quality gate (what CI runs)

# ---------- Load / smoke testing ----------
.PHONY: smoke
smoke: ## k6 smoke test against BASE_URL (default localhost:8000; requires k6)
	k6 run scripts/k6/smoke.js

.PHONY: load
load: ## Heavier k6 load test (50 VUs, 2m)
	k6 run --vus 50 --duration 2m scripts/k6/smoke.js

# ---------- Kubernetes ----------
.PHONY: k8s-dev
k8s-dev: ## Render the dev overlay (kustomize) to stdout
	kubectl kustomize infra/k8s/overlays/dev

.PHONY: k8s-apply-dev
k8s-apply-dev: ## Apply the dev overlay to the current kube-context
	kubectl apply -k infra/k8s/overlays/dev
