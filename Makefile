.PHONY: smoke contract-matrix pytest test help

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

help:
	@echo "Targets:"
	@echo "  smoke             Run mz-dev-pipe static smoke test (plumbing + fixture)"
	@echo "  contract-matrix   Validate agent terminal-state token documentation"
	@echo "  pytest            Run the Python test suite (hook scripts, Codex migration)"
	@echo "  test              Run all checks (contract-matrix + smoke + pytest)"

contract-matrix:
	@./plugins/mz-dev-pipe/tests/run_contract_matrix.sh

smoke:
	@./plugins/mz-dev-pipe/tests/smoke/run_smoke.sh

pytest:
	@$(PYTHON) -m pytest -q

test: contract-matrix smoke pytest
	@echo ""
	@echo "All checks passed."
