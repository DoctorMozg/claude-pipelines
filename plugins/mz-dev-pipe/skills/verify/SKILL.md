---
name: verify
description: 'Runs tests, linters and type checks and reports findings without editing code. Use when the user says "verify", "run tests", "lint the code" or "validate", or wants a quality gate. Not for fixing failures it finds (use polish, or debug for one bug).'
argument-hint: '[scope:branch|global|working] [optional focus — e.g. "src/auth/", "test_payments.py", "check examples work"]'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, AskUserQuestion, WebFetch, WebSearch
---

# Code Verification Pipeline

## Overview

Orchestrates a deep verification pass that checks whether code in scope is correct, clean, well-tested, and functional. This pipeline reports findings — it does NOT auto-fix anything. The user decides what to fix based on the report.

## When to Use

A read-only pass/fail snapshot of tests, lint, type safety and coverage before shipping or reviewing; it reports findings and never fixes them.

### When NOT to use

- Failing tests that need fixing — use `polish` or `debug`.
- New feature work that includes tests — use `build`.
- Hunting bugs or security issues by reading the code — use `audit`, which also reports without fixing.

## Input

- `$ARGUMENTS` — Optional scope and focus. Any combination of:
  - **Path/glob**: `"src/auth/"`, `"tests/test_payments.py"` — which files to verify
  - **Free-text focus**: `"check examples work"`, `"verify the API layer"` — what to focus on
  - **Combined**: `"src/payments/ check all edge cases are tested"`

If empty, verify the entire project (roam mode with standard exclusions).

## Scope Parameter

See `<PLUGIN_ROOT>/shared/scope-parameter.md` for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default** (no `scope:`): path/glob detection from argument, or roam entire project if empty.
- `scope:` determines **which source files** are under verification. Tests always run fully (not filtered) to catch regressions. Coverage and quality analysis focus on code within scope.

## Constants

- **PROJECT_ROOT**: resolved once in setup with `echo "${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"`; expand `<PROJECT_ROOT>` to it in every command and agent prompt.
- **TASK_DIR**: `<PROJECT_ROOT>/.mz/task/` — working artifacts under `<PROJECT_ROOT>/.mz/task/<task_name>/`
- **MAX_RESEARCHERS**: 3 — for failure diagnosis and coverage/quality review
- **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`. Skill and phase files write `<PLUGIN_ROOT>/...` because files opened with Read get no variable substitution; expand it to this absolute path before reading a file, running a command, or passing a path to an agent.

## Core Process

### Phase Overview

| #   | Phase                       | Reference          | Loop? |
| --- | --------------------------- | ------------------ | ----- |
| 0   | Setup                       | inline below       | —     |
| 1   | Scope Resolution            | `phases/setup.md`  | —     |
| 2   | Tooling Detection           | `phases/setup.md`  | —     |
| 3   | Execution                   | `phases/checks.md` | —     |
| 4   | Coverage & Quality Analysis | `phases/checks.md` | —     |
| 5   | Failure Diagnosis           | `phases/checks.md` | —     |
| 6   | Report                      | `phases/checks.md` | —     |

### Phase 0: Setup

1. **Project root** — resolve `PROJECT_ROOT` with the command in Constants, before any `cd` or worktree switch, and use it for every `.mz/` path below.
1. **Parse argument** — split (after removing `scope:`) into path-like tokens (globs, dirs, files) and focus tokens (free text).
1. **Task name** — `<YYYY_MM_DD>_verify_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is snake_case (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. **Resume check** (before creating the task directory): follow `<PLUGIN_ROOT>/shared/resume-protocol.md`, "On entry". A `complete`, `completed` or `aborted_by_user` file starts a `_vN`. A `pending`, `running`, `blocked` or `failed` file gets the resume gate. When the run is unattended or nobody can answer, report the path, `Status` and `what_remains`, and stop.
1. **Task dir & state** — run `mkdir -p "<PROJECT_ROOT>/.mz/task/<task_name>"` and write `state.md` per `<PLUGIN_ROOT>/shared/state-schema.md` — first line MUST be `schema_version: 2`, followed by `Status`, `Phase`, `Started`, plus the progress-ledger keys `phase_complete: false` and `what_remains: []`.
1. **Task tracking** — TaskCreate per pipeline phase.

### Phase 1–6

- **Phase 1 — Scope Resolution**: resolve argument into source, test, and example files. See `phases/setup.md` → Phase 1. Set `Phase: scope_resolved`.
- **Phase 2 — Tooling Detection**: detect test frameworks, linters, formatters, type checkers, example runners. See `phases/setup.md` → Phase 2. Set `Phase: tooling_detected`.
- **Phase 3 — Execution**: run all detected tools, capture results. See `phases/checks.md` → Phase 3. Set `Phase: checks_executed`.
- **Phase 4 — Coverage & Quality Analysis**: dispatch coverage and quality reviewer agents for code in scope. See `phases/checks.md` → Phase 4. Set `Phase: analysis_complete`.
- **Phase 5 — Failure Diagnosis**: if any Phase 3 check failed, dispatch researchers; skip if green. See `phases/checks.md` → Phase 5. Set `Phase: diagnosis_complete`.
- **Phase 6 — Report**: compile results, write to `<PROJECT_ROOT>/.mz/reports/<YYYY_MM_DD>_test_<scope_name>.md` (append `_v2`, `_v3` if exists). See `phases/checks.md` → Phase 6. Set `Status: complete`, `phase_complete: true`, `what_remains: []`.

## Common Rationalizations

| Rationalization                      | Rebuttal                                                           |
| ------------------------------------ | ------------------------------------------------------------------ |
| "tests passed last time, skip rerun" | "environment drift silently breaks suites between runs"            |
| "type-check is slow, skip"           | "the bug you didn't type-check is the one that crashes in staging" |
| "coverage is a vanity metric"        | "coverage < 70% means you're shipping blind in the uncovered 30%"  |

## Red Flags

- Type-check was skipped because it was "slow".
- Tests were declared passing without running them fresh in this session.
- Coverage delta was not measured against the scope.

## Verification

Output the final report block: per-check pass/fail status, coverage percentages, top quality findings, and the written report path. No silent skips.

## Error Handling

- **No test framework detected**: ask the user for a test command. Do not skip.
- **No linter detected**: note it in the report, skip lint checks.
- **No formatter detected**: note it in the report, skip format checks.
- **No type checker configured**: note it in the report, skip type checks. Do NOT suggest adding one.
- **Test command times out**: report timeout with partial output, flag in report.
- **Example script crashes**: capture the error output, include in report, do not retry.
- **Ambiguous scope**: ask the user to clarify.
- **Empty scope**: report and exit.

## State Management

After each phase, update `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` with:

- Current phase
- Per-check results (pass/fail/skip)
- Any issues encountered

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a verification gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, in the form `- (review|failure|correction|change) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`.
