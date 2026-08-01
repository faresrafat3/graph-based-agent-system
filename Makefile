.PHONY: install compile test coverage audit ci

PYTHON ?= python
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PIP) install -r requirements.txt

compile:
	$(VENV_PYTHON) -m compileall llm agents memory tools benchmarks tests scripts system main.py

test:
	$(VENV_PYTHON) -m pytest -q

coverage:
	$(VENV_PYTHON) -m pytest --cov=. --cov-report=term-missing --cov-fail-under=80 -q

audit:
	$(VENV_PYTHON) scripts/audit_stepfun_policy.py
	$(VENV_PYTHON) scripts/audit_governance.py

ci: compile audit coverage
