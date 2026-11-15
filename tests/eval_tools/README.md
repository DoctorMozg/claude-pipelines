# Plugin evals

The cases live in `evals/<plugin>/**/case.yaml`, in the `claude plugin eval` 1.1 format. They stay
the source of truth: `make eval` converts them afresh to mzeval cases under `.mz/mzeval-cases/` on
every run, then runs them with [mzeval](https://github.com/DoctorMozg/mozg-eval-pipelines), pinned
in the Makefile. Keep prompts, fixtures, graders, dependencies and trial counts in the 1.1 files.

Run from the repository root after signing in to the agent's CLI. These commands make paid model
calls; `uvx` fetches mzeval on first use.

```sh
make eval PLUGIN=mz-memory
make eval PLUGIN=mz-memory EVAL_DRIVER=codex
make eval PLUGIN=all EVAL_RUNS=1 EVAL_ARGS="--case 'inject-*'"
```

`EVAL_MODEL` defaults to `sonnet` on Claude and `gpt-6.1-sol` on Codex. `EVAL_RUNS` overrides each
case's `runs`. `EVAL_MAX_USD` caps agent and judge spend for the run, and no trial starts once it is
reached. `EVAL_ABLATION=with-without` adds the arm without the plugin. `EVAL_ARGS` passes extra
`mzeval run` flags, such as `--case <glob>` or `--tag <tag>`.

Judge graders use `EVAL_JUDGE` (`anthropic:claude-haiku-5-5`), which reads `ANTHROPIC_API_KEY` from
the environment. A suite with no judge grader needs no key.

Each trial gets a fresh temp workspace, initialised as a git repository, and a temp HOME. The
case's `allowed_tools` are the only tools offered, with permissions bypassed and no OS sandbox, so
a shell command can write the workspace. That is safe only because every case and fixture here is
written in this repo. Results land in `.mzeval/`, and `mzeval report`, run through the same pinned `uvx` command as the
Makefile's `MZEVAL`, writes an HTML report of the latest run.

The import writes `.mz/mzeval-cases/migration-report.md`, which lists each grader it rewrote and
why. Codex can't enforce a case's tool list, and cases that only Claude's trace can grade are
skipped on other agents with the reason printed.

## Mutants and prechecks

`make test` checks the suites for free: every mutant in `mutant_catalog.py` still finds its anchor,
and the mz-memory and tooling prechecks run a case's fixture and the real hooks through
`local_graders.py`. `make eval-mutants MUTANTS=<id ...>` is the paid check. It breaks plugin code in
a HEAD snapshot and confirms the cases fail. It still runs `claude plugin eval`, because mzeval has
no mutation runner yet.

## Hooks in an interactive Codex session

To install converted hooks for normal interactive sessions, use a fresh output directory:

```sh
.venv/bin/python -m mozg_pipelines.codex_hooks render mz-memory --output /tmp/mz-memory-codex
.venv/bin/python -m mozg_pipelines.codex_hooks install /tmp/mz-memory-codex
.venv/bin/python -m mozg_pipelines.codex_hooks doctor
```

Installation runs a paid delivery probe. Review the registered definitions through
Codex's normal `/hooks` interface. The installer owns only its own registrations
and keeps private package snapshots; removing the temporary render directory does
not break them. `uninstall mz-memory` removes those registrations. `doctor --live`
runs another paid probe. After a CLI version change, inspect compatibility and
reinstall as needed.

Converted memory hooks use the Codex curator backend. `MZ_MEMORY_COMPRESS=0` disables
maintenance; `MZ_CODEX_MEMORY_CURATOR_MODEL` selects its model. The curator uses an
isolated, bounded, tool-free structured-output session and the existing shared
operation validation. It does not implement Claude's dollar-cost cap.
