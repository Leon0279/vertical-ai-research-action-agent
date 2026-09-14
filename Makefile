VENV_PYTHON := .venv/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
UVICORN := $(VENV_PYTHON) -m uvicorn
PYCACHE_PREFIX := /private/tmp/vaa-pyc
COMPOSE := docker compose

.PHONY: check-venv test test-unit run preflight volumes dev status logs smoke smoke-live test-docker down reset-data adopt-local-data

check-venv:
	@test -x "$(VENV_PYTHON)" || (echo "Missing $(VENV_PYTHON). Create the project virtualenv first." && exit 1)

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
	@echo "Logs:    make logs"

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --follow api redis postgres

smoke:
	@./scripts/smoke.sh

smoke-live:
	@CONFIRM_PAID="$(CONFIRM_PAID)" ./scripts/live_smoke.sh

test-docker:
	$(COMPOSE) run --rm --no-deps api python -m pytest tests

down:
	$(COMPOSE) down --remove-orphans

reset-data:
	@if [ "$(CONFIRM_RESET)" != "YES" ]; then echo "Refusing to delete local data without CONFIRM_RESET=YES."; exit 1; fi
	$(COMPOSE) down --remove-orphans
	docker volume rm vaa-postgres-data vaa-redis-data

adopt-local-data:
	@ALLOW_LEGACY_CONTAINERS=1 ./scripts/preflight.sh
	@CONFIRM_ADOPT="$(CONFIRM_ADOPT)" ./scripts/adopt_local_data.sh
