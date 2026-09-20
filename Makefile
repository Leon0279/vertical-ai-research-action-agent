VENV_PYTHON := .venv/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
UVICORN := $(VENV_PYTHON) -m uvicorn
PYCACHE_PREFIX := /private/tmp/vaa-pyc
COMPOSE := docker compose
NPM := npm
FRONTEND_DIR := frontend

.PHONY: check-venv check-node test test-unit run preflight volumes dev status logs smoke smoke-frontend smoke-all smoke-live test-docker frontend-install frontend-generate frontend-dev frontend-typecheck frontend-lint frontend-test frontend-build frontend-check down reset-data adopt-local-data

check-venv:
	@test -x "$(VENV_PYTHON)" || (echo "Missing $(VENV_PYTHON). Create the project virtualenv first." && exit 1)

check-node:
	@command -v node >/dev/null 2>&1 || (echo "Missing Node.js 24 LTS. Install it before running frontend commands." && exit 1)
	@node -e 'const major=Number(process.versions.node.split(".")[0]); if (major !== 24) { console.error("Node.js 24 LTS is required; found " + process.versions.node); process.exit(1); }'

test: check-venv
	PYTHONPYCACHEPREFIX="$(PYCACHE_PREFIX)" $(PYTEST) tests

test-unit: check-venv
	PYTHONPYCACHEPREFIX="$(PYCACHE_PREFIX)" $(PYTEST) tests/app

run: check-venv
	$(UVICORN) main:app --reload --host 127.0.0.1 --port 8000

preflight:
	@./scripts/preflight.sh

volumes:
	@docker volume inspect vaa-postgres-data >/dev/null 2>&1 || docker volume create vaa-postgres-data >/dev/null
	@docker volume inspect vaa-redis-data >/dev/null 2>&1 || docker volume create vaa-redis-data >/dev/null

dev: preflight volumes
	@mkdir -p logs
	$(COMPOSE) up --build --detach --wait
	@api_address=`$(COMPOSE) port api 8000`; echo "API:     http://$$api_address"
	@api_address=`$(COMPOSE) port api 8000`; echo "Swagger: http://$$api_address/docs"
	@frontend_address=`$(COMPOSE) port frontend 80`; echo "Frontend: http://$$frontend_address"
	@echo "Logs:    make logs"

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --follow api frontend redis postgres

smoke:
	@./scripts/smoke.sh

smoke-frontend:
	@./scripts/smoke_frontend.sh

smoke-all: smoke smoke-frontend

smoke-live:
	@CONFIRM_PAID="$(CONFIRM_PAID)" ./scripts/live_smoke.sh

test-docker:
	$(COMPOSE) run --rm --no-deps api python -m pytest tests

frontend-install: check-node
	$(NPM) --prefix $(FRONTEND_DIR) install

frontend-generate: check-venv check-node
	$(VENV_PYTHON) scripts/export_openapi.py
	$(NPM) --prefix $(FRONTEND_DIR) run generate:api

frontend-dev: check-node
	$(NPM) --prefix $(FRONTEND_DIR) run dev

frontend-typecheck: check-node
	$(NPM) --prefix $(FRONTEND_DIR) run typecheck

frontend-lint: check-node
	$(NPM) --prefix $(FRONTEND_DIR) run lint

frontend-test: check-node
	$(NPM) --prefix $(FRONTEND_DIR) run test

frontend-build: check-node
	$(NPM) --prefix $(FRONTEND_DIR) run build

frontend-check: frontend-typecheck frontend-lint frontend-test frontend-build

down:
	$(COMPOSE) down --remove-orphans

reset-data:
	@if [ "$(CONFIRM_RESET)" != "YES" ]; then echo "Refusing to delete local data without CONFIRM_RESET=YES."; exit 1; fi
	$(COMPOSE) down --remove-orphans
	docker volume rm vaa-postgres-data vaa-redis-data

adopt-local-data:
	@ALLOW_LEGACY_CONTAINERS=1 ./scripts/preflight.sh
	@CONFIRM_ADOPT="$(CONFIRM_ADOPT)" ./scripts/adopt_local_data.sh
