# Plugin eval runners

Both runners read the existing `evals/<plugin>/**/case.yaml` cases. Keep prompts,
fixtures, graders, dependencies, and trial counts there; do not create a separate
Codex case tree.

Run from the repository root after installing the Python development dependencies
and signing in to the relevant CLI. These commands make paid model calls by default.

```sh
make eval PLUGIN=mz-memory
make eval-codex PLUGIN=mz-memory
make eval-codex PLUGIN=all CODEX_MODEL=gpt-6.1-sol EVAL_JOBS=4
```

`EVAL_RUNS=3` overrides each case's `runs`. Without an override, the canonical value
is used, defaulting to one trial. `EVAL_JOBS` accepts 1–8 for Codex. To select a
case, match its name or its path relative to `evals`:

```sh
make eval-codex PLUGIN=mz-memory \
  EVAL_ARGS='--case=inject-pinned-fact --retain-sessions'
make eval-codex PLUGIN=all \
  EVAL_ARGS='--case=mz-memory/* --output-dir .mz/eval-runs/memory-check'
```

Use an existing case name when filtering. A filter with no matches fails before
execution. Output directories must be empty or absent; a new invocation never
overwrites an earlier run.

## What the Codex runner does

The runner renders the packages allowed by `data/codex_migration.toml` once, freezes
their provenance, and installs only each case's declared `plugins:` dependencies
in its isolated Codex home. An unavailable dependency produces a case error.
Changes to a case or its fixture inputs after discovery also produce an error.

Direct Claude skill invocations are translated to Codex skill requests. Explicit
Claude file-tool names receive native tool guidance, including `apply_patch` for
Write/Edit. The requested text and quoted file content remain intact in the
derived prompt, which is saved with the original case specification.

One model-backed probe checks native hook delivery. If the native plugin probe
emits no events and the user-hook control succeeds, the runner registers converted
hooks through its isolated bridge. Inconclusive delivery fails setup. The temporary
eval home trusts its derived hooks; this does not change the user's hook trust.
Memory maintenance is disabled during evals to avoid detached model calls; the
Codex maintenance backend has separate tests.

All current case fields are read, but the current runner does not enforce an
equivalent of Claude `allowed_tools` or `max_turns`; these are reported as limitations.
Claude-specific `Skill`, named `Agent`, and file-tool
wire assertions remain unsupported. Canonical `hook_response` assertions use
verified SessionStart I/O to match the Claude eval trace's event scope. All actual
hook events and the raw Codex trace are retained separately.

Each assertion reports `pass`, `fail`, or `unsupported`. A case is `fail` if any
supported assertion fails, otherwise `unsupported` if any assertion is unsupported,
otherwise `pass`. Execution failures are `error`. Unsupported assertions never
count as passes. The Python runner exits 1 if any case is not fully passing, 2 for a
setup error, and 130 for interruption. Make reports a failed recipe as its own
nonzero exit status. Check `metadata.json.completed` separately from the exit code
to determine whether the batch finished.

## Evidence

The default destination is `evals/results/codex-<timestamp>/`. It and the usual
per-plugin results directories are ignored by Git. A run retains:

- `metadata.json`: completion, runtime, package and source provenance.
- `results.jsonl`: incremental case outcomes; `results.json`: final sorted outcomes.
- Per-trial source specification, fixture hashes, initial and final workspace files.
- CLI arguments, stdout, stderr, exit status, timings, parsed events, and usage.
- Actual hook commands, input, output, exit status, and normalized hook responses.
- `skill-evidence.json`: verified skill loads and attributable packaged-script actions.
- Native session rollouts when `--retain-sessions` is supplied.

Skill evidence is separate from canonical grades. `loaded` means a successful,
complete `cat` of the installed skill body matched its frozen package bytes.
`workflow-observed` adds a later successful invocation of a packaged script uniquely
referenced by that skill's main body. Each observation retains the one-based trace
event ordinal, item ID, command, installed path, and file hash. The catalog is frozen
before execution, and its analyzer source hash is included in runtime provenance.

Result JSON includes `skill_evidence` and per-assertion `skill_assessments`. Positive
Skill existence assertions can show the portable evidence state; their canonical
grade stays `unsupported`. Loading or running a checker can also occur during
inspection, so neither state proves native activation or full workflow completion.
Negative and count assertions remain `unknown`. Missing observations cannot prove
non-use: the observer recognizes only conservative literal command forms in root
CLI events, with no child-thread or injected-body coverage. Failed and partial
executions retain evidence but receive no assertion grades or assessments.

Temporary auth links or refreshed auth files are removed after each trial. Retained
traces can contain fixture and model content. CLI token counters describe their
reported scope; they are not a dollar-cost estimate or an automatic sum of all
native subagent usage.

## Replay retained skill evidence

Replay uses recorded case specifications, CLI traces, installed caches, and each
run's frozen packages. It starts no subprocesses or model calls:

```sh
.venv/bin/python -m tests.eval_tools.codex_skill_replay \
  --index .mz/task/2026_11_06_build_codex_hooks/latest-results.json \
  --output-dir .mz/eval-runs/codex-skill-replay
```

The destination must be absent and outside every historical run. Replay preserves
all original result fields and adds evidence, assessments, and validation details.
The index must contain historical results without `skill_evidence`,
`skill_assessments`, or `evidence_validation`; rows already containing derived
fields are rejected before writing. Current runner results already include evidence.
It writes incremental `results.jsonl`, final `results.json`, separate evidence
counts in `summary.json`, per-trial sidecars, and a fingerprint `manifest.json`.

Validation checks canonical source and fixture hashes, the recorded specification,
result agreement, full frozen package inventories, requested installed skill bodies
and attributable scripts, and existing historical root seals. Invalid inputs leave
that row's portable assessments empty. Known original missing-dependency errors
remain reportable, and partial executions retain observations without assessments.
Completed executions must also have a successful native trace and final message.
Historical executor source drift is disclosed because replay uses a new analyzer.
Old root seals do not cover per-case raw traces or installed caches; their replay
hashes are fresh fingerprints, not evidence that those files were historically sealed.

Exit status is 0 when all retained inputs validate, including original unsupported
or failed executions; 1 when any row fails evidence validation; and 2 for invalid
selection, destination setup, or output I/O. Failed writes leave the initial
manifest incomplete. Replay never changes a canonical grade.

## Hooks in an interactive Codex session

The eval runner's registrations are isolated. To install converted hooks for normal
interactive sessions, use a fresh output directory:

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
