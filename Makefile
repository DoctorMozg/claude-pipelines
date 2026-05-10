.PHONY: smoke contract-matrix test help

help:
	@echo "Targets:"
	@echo "  smoke             Run mz-dev-pipe static smoke test (plumbing + fixture)"
	@echo "  contract-matrix   Validate agent terminal-state token documentation"
	@echo "  test              Run all checks (contract-matrix + smoke)"

contract-matrix:
	@./plugins/mz-dev-pipe/tests/run_contract_matrix.sh

smoke:
	@./plugins/mz-dev-pipe/tests/smoke/run_smoke.sh

test: contract-matrix smoke
	@echo ""
	@echo "All checks passed."
