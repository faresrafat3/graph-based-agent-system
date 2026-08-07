.PHONY: install compile test coverage audit ci benchmark benchmark-extended report clean-reports improve improve-safe prune systems-layer

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

# Strict audit: tracked WARNINGS fail too. This is what CI runs.
audit-strict:
	$(VENV_PYTHON) scripts/audit_stepfun_policy.py
	$(VENV_PYTHON) scripts/audit_governance.py --strict

# Governed self-improvement meta-loop (META-SYSTEM.md)
improve:
	$(VENV_PYTHON) scripts/run_improvement_cycle.py --measurements-dir system/measurements

improve-safe:
	$(VENV_PYTHON) scripts/run_improvement_cycle.py --safe-only --measurements-dir system/measurements

# Systems Layer in-graph cycle + opus-5 live review (reconciliation v2+)
systems-layer:
	$(VENV_PYTHON) scripts/run_systems_layer.py --opus5

# P7 self-pruning report (advisory; never deletes)
prune:
	$(VENV_PYTHON) system/self_pruning.py

benchmark:
	$(VENV_PYTHON) scripts/run_benchmarks.py

benchmark-extended:
	$(VENV_PYTHON) scripts/run_benchmarks.py --extended

report:
	@ls -lh reports/ || echo "No reports dir"
	@cat reports/latest_benchmark.md 2>/dev/null || echo "No latest report yet, run make benchmark"

clean-reports:
	rm -rf reports/*.json reports/*.md
	@echo "Reports cleaned, keeping dir"
	mkdir -p reports
	touch reports/.gitkeep

ci: compile audit coverage

full-ci: compile audit coverage benchmark
	@echo "Full CI with benchmarks complete"
