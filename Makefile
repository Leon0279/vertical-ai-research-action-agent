VENV_PYTHON := .venv/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
PYCACHE_PREFIX := /private/tmp/vaa-pyc

.PHONY: check-venv test test-unit

check-venv:
	@test -x "$(VENV_PYTHON)" || (echo "Missing $(VENV_PYTHON). Create the project virtualenv first." && exit 1)

test: check-venv
	PYTHONPYCACHEPREFIX="$(PYCACHE_PREFIX)" $(PYTEST) tests

test-unit: check-venv
	PYTHONPYCACHEPREFIX="$(PYCACHE_PREFIX)" $(PYTEST) tests/unit
