.PHONY: smoke contract-matrix pytest test validate help

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CLAUDE ?= claude

help:
	@echo "Targets:"
	@echo "  smoke             Run mz-dev-pipe static smoke test (plumbing + fixture)"
	@echo "  contract-matrix   Validate agent terminal-state token documentation"
	@echo "  pytest            Run the Python test suite (hook scripts, Codex migration)"
	@echo "  test              Run all checks (contract-matrix + smoke + pytest)"
	@echo "  validate          Run claude plugin validate --strict on the marketplace and every plugin"

contract-matrix:
	@./plugins/mz-dev-pipe/tests/run_contract_matrix.sh

smoke:
	@./plugins/mz-dev-pipe/tests/smoke/run_smoke.sh

pytest:
	@$(PYTHON) -m pytest -q

test: contract-matrix smoke pytest
	@echo ""
	@echo "All checks passed."

# Validates every target before failing, so one run lists every broken plugin.
validate:
	@failed=""; \
	for target in . plugins/*/; do \
		if ! output=$$($(CLAUDE) plugin validate --strict "$$target" 2>&1); then \
			printf '%s\n' "$$output"; \
			failed="$$failed $$target"; \
		fi; \
	done; \
	if [ -n "$$failed" ]; then echo "validate --strict failed:$$failed"; exit 1; fi; \
	echo "validate --strict passed: marketplace and $$(ls -d plugins/*/ | wc -l) plugins"
