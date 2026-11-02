.PHONY: smoke contract-matrix pytest test validate gh-smoke eval help

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CLAUDE ?= claude
EVAL_MODEL ?= sonnet
# Pinned, so judge-scored results stay comparable across runs and releases.
EVAL_JUDGE ?= claude-haiku-5-5
EVAL_MAX_USD ?= 5
EVAL_RUNS ?=
# Each job is a full claude child on your credential, so jobs share one rate limit.
EVAL_JOBS ?= 4

help:
	@echo "Targets:"
	@echo "  smoke             Run mz-dev-pipe static smoke test (plumbing + fixture)"
	@echo "  contract-matrix   Validate agent terminal-state token documentation"
	@echo "  pytest            Run the Python test suite (hook scripts, Codex migration)"
	@echo "  test              Run all checks (contract-matrix + smoke + pytest)"
	@echo "  validate          Run claude plugin validate --strict on the marketplace and every plugin"
	@echo "  gh-smoke          Run the mz-dev-git GitHub collectors live (needs gh auth, spends tokens)"
	@echo "  eval PLUGIN=<n>   Run a plugin's eval suite (EVAL_MODEL, EVAL_RUNS, EVAL_JOBS, EVAL_MAX_USD; spends tokens)"

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

# Live GitHub and model calls, so it stays out of `test` and CI.
gh-smoke:
	@$(PYTHON) -I tests/e2e/gh_smoke.py

# Targets the repo root so a case's `plugins:` may also load sibling plugins: dependencies and
# cross-plugin near misses. Routing needs no baseline arm, and --trust-plugin covers only this repo.
eval:
	@test -n "$(PLUGIN)" || { echo "usage: make eval PLUGIN=<name> [EVAL_MODEL=opus] [EVAL_RUNS=1]"; exit 2; }
	@test -d "plugins/$(PLUGIN)/evals" || { echo "plugins/$(PLUGIN) has no evals/ directory"; exit 2; }
	@mkdir -p "plugins/$(PLUGIN)/evals/results"
	$(CLAUDE) plugin eval . --eval-dir "plugins/$(PLUGIN)/evals" --ablation none --trust-plugin --no-publish \
		--model "$(EVAL_MODEL)" --judge-model "$(EVAL_JUDGE)" --max-cost-usd "$(EVAL_MAX_USD)" -j "$(EVAL_JOBS)" \
		$(if $(EVAL_RUNS),--runs "$(EVAL_RUNS)") \
		--json "plugins/$(PLUGIN)/evals/results/last-$(EVAL_MODEL).json"
