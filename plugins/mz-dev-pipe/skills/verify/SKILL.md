---
name: verify
description: ALWAYS invoke when the user wants to verify code quality, run tests, lint, or check type safety. Triggers: "verify", "run tests", "check code quality", "lint the code", "validate". Deep verification pipeline — runs tests, linters, formatters, type checkers, analyzes coverage and quality, checks examples, and diagnoses failures. Produces a pass/fail report. Provide scope as the argument.
argument-hint: [scope:branch|global|working] [optional focus — e.g. "src/auth/", "test_payments.py", "check examples work"]
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Verification Pipeline

You orchestrate a deep verification pass that checks whether code in scope is correct, clean, well-tested, and functional. This pipeline reports findings — it does NOT auto-fix anything. The user decides what to fix based on the report.

## Input

- `$ARGUMENTS` — Optional scope and focus. Any combination of:
  - **Path/glob**: `"src/auth/"`, `"tests/test_payments.py"` — which files to verify
  - **Free-text focus**: `"check examples work"`, `"verify the API layer"` — what to focus on
  - **Combined**: `"src/payments/ check all edge cases are tested"`

If empty, verify the entire project (roam mode with standard exclusions).

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, >5000 LOC).                                                                                           |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): use path/glob detection from argument, or roam the entire project if empty.

The `scope:` parameter determines **which source files** are under verification. Tests always run fully (not filtered by scope) to catch regressions. Coverage and quality analysis focus on code within scope.

## Constants

- **TASK_DIR**: `.mz/task/` — working artifacts under `.mz/task/<task_name>/`
- **MAX_RESEARCHERS**: 3 — for failure diagnosis and coverage/quality review

## Phase Overview

| #   | Phase                       | Reference          | Loop? |
| --- | --------------------------- | ------------------ | ----- |
| 0   | Setup                       | inline below       | —     |
| 1   | Scope Resolution            | `phases/setup.md`  | —     |
| 2   | Tooling Detection           | `phases/setup.md`  | —     |
| 3   | Execution                   | `phases/checks.md` | —     |
| 4   | Coverage & Quality Analysis | `phases/checks.md` | —     |
| 5   | Failure Diagnosis           | `phases/checks.md` | —     |
| 6   | Report                      | `phases/checks.md` | —     |

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse argument

Split `$ARGUMENTS` (after removing `scope:` parameter) into:

- **Path-like tokens**: globs, directories, file paths
- **Focus tokens**: everything else — the user's focus area or question

### 0.2 Derive task name

Short snake_case name (max 30 chars). Examples: `test_full_project`, `test_branch_changes`, `test_src_auth`.

### 0.3 Create task directory and state

Create `.mz/task/<task_name>/` directory. Write `state.md` with Status, Phase, and Started fields.

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

______________________________________________________________________

## Phase 1: Scope Resolution

Resolve the argument into source files, test files, and example/sample files.

**See `phases/setup.md` → Phase 1** for file resolution rules, test file mapping, and the `scope.md` artifact.

Update state phase to `scope_resolved`.

______________________________________________________________________

## Phase 2: Tooling Detection

Detect test frameworks, linters, formatters, type checkers, and example runners.

**See `phases/setup.md` → Phase 2** for the detection tables, `tooling.md` artifact, and missing-framework escalation.

Update state phase to `tooling_detected`.

______________________________________________________________________

## Phase 3: Execution

Run all detected tools and capture results.
**See `phases/checks.md` → Phase 3** for execution order, output capture, and the per-check result format.
Update state phase to `checks_executed`.

______________________________________________________________________

## Phase 4: Coverage & Quality Analysis

Dispatch coverage and quality reviewer agents for code in scope.
**See `phases/checks.md` → Phase 4** for dispatch prompts and result artifacts.
Update state phase to `analysis_complete`.

______________________________________________________________________

## Phase 5: Failure Diagnosis

If any Phase 3 check failed, dispatch researchers to diagnose root causes. Skip if all passed.
**See `phases/checks.md` → Phase 5** for the diagnosis dispatch prompt and result artifact.
Update state phase to `diagnosis_complete`.

______________________________________________________________________

## Phase 6: Report

Compile all results into a single report.
**See `phases/checks.md` → Phase 6** for the full report template.
Write to `.mz/reports/test_<YYYY_MM_DD>_<scope_name>.md` (append `_v2`, `_v3` if exists). Update state to `completed`. Present a summary to the user with the report path.

______________________________________________________________________

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
