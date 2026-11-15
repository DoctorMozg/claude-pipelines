.PHONY: smoke contract-matrix pytest test validate vendor-shared gh-smoke hooks-smoke gate-smoke eval eval-mutants help

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
CLAUDE ?= claude
# Pinned, so a run is reproducible; bump the sha to take a newer mzeval.
MZEVAL ?= uvx --from git+https://github.com/DoctorMozg/mozg-eval-pipelines@1e282a2 mzeval
EVAL_DRIVER ?= claude
EVAL_MODEL ?= $(if $(filter codex,$(EVAL_DRIVER)),gpt-6.1-sol,sonnet)
# Pinned, so judge-scored results stay comparable across runs and releases. Needs ANTHROPIC_API_KEY.
EVAL_JUDGE ?= anthropic:claude-haiku-5-5
EVAL_MAX_USD ?= 5
EVAL_RUNS ?=
# Each job is a model session on your credential, so jobs share one rate limit.
EVAL_JOBS ?= 4
# Routing and hook cases need no baseline; set with-without to measure what a plugin adds.
EVAL_ABLATION ?= none
# Extra flags for one run, such as `--tag inject` or `--case 'capture-*'`.
EVAL_ARGS ?=
# The mutants tool still runs `claude plugin eval`, whose judge takes a bare Claude model name.
MUTANTS_JUDGE ?= claude-haiku-5-5
EVAL_SRC = $(if $(filter all,$(PLUGIN)),evals,evals/$(PLUGIN))
EVAL_CASES = .mz/mzeval-cases/$(notdir $(EVAL_SRC))

help:
	@echo "Targets:"
	@echo "  smoke             Run mz-dev-pipe static smoke test (plumbing + fixture)"
	@echo "  contract-matrix   Validate agent terminal-state token documentation"
	@echo "  pytest            Run the Python test suite (hook scripts, Codex migration)"
	@echo "  test              Run all checks (contract-matrix + smoke + pytest)"
	@echo "  validate          Run claude plugin validate --strict on the marketplace and every plugin"
	@echo "  vendor-shared     Copy plugins/mz-base/shared into every other plugin that has a shared/ folder"
	@echo "  gh-smoke          Run the mz-dev-git GitHub collectors live (needs gh auth, spends tokens)"
	@echo "  hooks-smoke       Run the memory, tooling and vault hooks in live headless sessions (spends tokens)"
	@echo "  gate-smoke        Answer memory-note and polish gates headlessly, check the journal (spends tokens)"
	@echo "  eval PLUGIN=<n|all> Run a plugin's eval suite with mzeval (EVAL_DRIVER, EVAL_MODEL, EVAL_RUNS,"
	@echo "                    EVAL_JOBS, EVAL_MAX_USD, EVAL_ABLATION, EVAL_JUDGE, EVAL_ARGS; spends tokens)"
	@echo "  eval-mutants      Break plugin code in a HEAD snapshot and check the evals catch it"
	@echo "                    (MUTANTS=<id ...>, all by default; EVAL_MODEL, MUTANTS_JUDGE, EVAL_JOBS; spends tokens)"

contract-matrix:
	@./tests/mz_dev_pipe_contracts/run_contract_matrix.sh

smoke:
	@./tests/mz_dev_pipe_contracts/smoke/run_smoke.sh

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

# Anthropic's directory blocks plugins that load symlinks, so each consumer carries a real copy.
# Edit only mz-base/shared; tests/plugin_lint/test_shared_copies.py fails when a copy drifts.
vendor-shared:
	@for copy in plugins/*/shared; do \
		[ "$$copy" = plugins/mz-base/shared ] && continue; \
		rm -rf "$$copy" && cp -R plugins/mz-base/shared "$$copy" && echo "vendored $$copy"; \
	done

# Live GitHub and model calls, so they stay out of `test` and CI. Run as modules so they share smoke_common.
gh-smoke:
	@$(PYTHON) -E -s -m tests.e2e.gh_smoke

hooks-smoke:
	@$(PYTHON) -E -s -m tests.e2e.hooks_smoke

# GATE_ARGS passes harness flags, such as `--scenario note-approve`.
gate-smoke:
	@$(PYTHON) -E -s -m tests.e2e.gate_smoke $(GATE_ARGS)

# The 1.1 case.yaml files stay the source; each run converts them afresh to mzeval cases under .mz/.
# Every suite and fixture script here is authored in this repo, which is what makes running them safe.
eval:
	@test -n "$(PLUGIN)" || { echo "usage: make eval PLUGIN=<name|all> [EVAL_DRIVER=codex] [EVAL_RUNS=1] [EVAL_ARGS=...]"; exit 2; }
	@test -d "$(EVAL_SRC)" || { echo "$(EVAL_SRC) does not exist"; exit 2; }
	@case "$(EVAL_ABLATION)" in none|with-without) ;; *) echo "EVAL_ABLATION must be none or with-without"; exit 2;; esac
	@rm -rf "$(EVAL_CASES)"
	$(MZEVAL) import claude-plugin-eval "$(EVAL_SRC)" --out .mz/mzeval-cases
	$(MZEVAL) run "$(EVAL_CASES)" --driver "$(EVAL_DRIVER)" --model "$(EVAL_MODEL)" --judge "$(EVAL_JUDGE)" \
		--max-cost-usd "$(EVAL_MAX_USD)" --jobs "$(EVAL_JOBS)" \
		$(if $(EVAL_RUNS),--runs "$(EVAL_RUNS)") $(if $(filter with-without,$(EVAL_ABLATION)),--ablation) $(EVAL_ARGS)

# Runs every mutant unless MUTANTS names some. The anchors are checked for free in `make test`.
MUTANTS ?=
eval-mutants:
	@$(PYTHON) -E -s -m tests.eval_tools.mutants --model "$(EVAL_MODEL)" --judge-model "$(MUTANTS_JUDGE)" \
		-j "$(EVAL_JOBS)" $(MUTANTS)
