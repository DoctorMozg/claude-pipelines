---
name: verify
description: ALWAYS invoke when the user wants to verify code quality, run tests, lint, or check type safety. Triggers: "verify", "run tests", "lint the code", "validate". When NOT to use: fixing failures (use polish or debug).
argument-hint: [scope:branch|global|working] [optional focus — e.g. "src/auth/", "test_payments.py", "check examples work"]
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Verification Pipeline

## Overview

Orchestrates a deep verification pass that checks whether code in scope is correct, clean, well-tested, and functional. This pipeline reports findings — it does NOT auto-fix anything. The user decides what to fix based on the report.

## When to Use

- User asks to verify, run tests, lint, type-check, or gate quality.
- Triggers: "verify", "run tests", "check code quality", "lint the code", "validate".
- You need a read-only pass/fail snapshot before shipping or reviewing.

### When NOT to use

- Failing tests that need fixing — use `polish` or `debug`.
- New feature work that includes tests — use `build`.
- Bug hunt with auto-fix — use `audit`.

## Input

- `$ARGUMENTS` — Optional scope and focus. Any combination of:
  - **Path/glob**: `"src/auth/"`, `"tests/test_payments.py"` — which files to verify
  - **Free-text focus**: `"check examples work"`, `"verify the API layer"` — what to focus on
  - **Combined**: `"src/payments/ check all edge cases are tested"`

If empty, verify the entire project (roam mode with standard exclusions).

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default** (no `scope:`): path/glob detection from argument, or roam entire project if empty.
- `scope:` determines **which source files** are under verification. Tests always run fully (not filtered) to catch regressions. Coverage and quality analysis focus on code within scope.

## Constants

- **TASK_DIR**: `.mz/task/` — working artifacts under `.mz/task/<task_name>/`
- **MAX_RESEARCHERS**: 3 — for failure diagnosis and coverage/quality review

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

1. **Parse argument** — split (after removing `scope:`) into path-like tokens (globs, dirs, files) and focus tokens (free text).
1. **Task name** — `<YYYY_MM_DD>_verify_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is snake_case (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. **Task dir & state** — create `.mz/task/<task_name>/`, write `state.md` with Status, Phase, Started.
1. **Task tracking** — TaskCreate per pipeline phase.

### Phase 1–6

- **Phase 1 — Scope Resolution**: resolve argument into source, test, and example files. See `phases/setup.md` → Phase 1. Update state to `scope_resolved`.
- **Phase 2 — Tooling Detection**: detect test frameworks, linters, formatters, type checkers, example runners. See `phases/setup.md` → Phase 2. Update state to `tooling_detected`.
- **Phase 3 — Execution**: run all detected tools, capture results. See `phases/checks.md` → Phase 3. Update state to `checks_executed`.
- **Phase 4 — Coverage & Quality Analysis**: dispatch coverage and quality reviewer agents for code in scope. See `phases/checks.md` → Phase 4. Update state to `analysis_complete`.
- **Phase 5 — Failure Diagnosis**: if any Phase 3 check failed, dispatch researchers; skip if green. See `phases/checks.md` → Phase 5. Update state to `diagnosis_complete`.
- **Phase 6 — Report**: compile results, write to `.mz/reports/<YYYY_MM_DD>_test_<scope_name>.md` (append `_v2`, `_v3` if exists). See `phases/checks.md` → Phase 6. Update state to `completed`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

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

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Per-check results (pass/fail/skip)
- Any issues encountered
