# Phases 6-8: Implementation (GREEN), Code Review, and Verify GREEN

Full detail for the implementation phases of the build skill. Coders are dispatched **after tests have been written, reviewed, and verified RED**. Their goal is to make the failing tests pass without modifying any test file. The phase ends when linters are clean and the full test suite is green.

## Contents

- [Phase 6: Implementation (GREEN)](#phase-6-implementation-green)
  - 6.1 Parse work units
  - 6.2 Execute waves
  - 6.3 Collect results
- [Phase 7: Code Review](#phase-7-code-review)
  - 7.1 Review code
  - 7.2 Handle verdict
- [Phase 8: Lint, Format, and Verify GREEN](#phase-8-lint-format-and-verify-green)
  - 8.1 Detect project tooling
  - 8.2 Run linters and formatters
  - 8.3 Run the full test suite
  - 8.4 Re-run linters after fixes

______________________________________________________________________

## Phase 6: Implementation (GREEN)

**Goal**: Make the Phase 3 tests pass without modifying any test file. Implement the plan using parallel coders where possible.

**Precondition**: Phase 5 must have completed with `red_verified`. Do NOT enter Phase 6 if any tests unexpectedly passed in Phase 5 — that means the test suite has gaps that no amount of implementation can close.

### 6.1 Parse work units

From the approved plan, extract all work units. Group them into execution waves:

- **Wave 1**: All units marked PARALLEL with no dependencies
- **Wave 2**: Units that depend on Wave 1 outputs
- **Wave N**: Continue until all units scheduled

For each work unit, identify the failing tests written in Phase 3 that target that unit (read `.mz/task/<task_name>/tests.md` for the work-unit-to-test mapping).

### 6.2 Execute waves

For each wave, spawn **one agent per work unit** in parallel.

Use `pipeline-coder` agent type for all work units. Model: **opus** for all coders.

Each coder agent prompt:

```
You are implementing one work unit of a larger task. Tests for this work unit ALREADY EXIST and are currently failing — your job is to make them pass.

## Overall Task
<task description>

## Plan
Read the full plan at .mz/task/<task_name>/plan.md for context.

## Your Work Unit
<specific work unit details>

## Your Failing Tests (the GREEN target)
<list of test files and test names that target this work unit, copied from .mz/task/<task_name>/tests.md>

Read .mz/task/<task_name>/red_run.md for the current failure output of these tests — that is the contract you must satisfy.

## TDD Mode — Read carefully
1. The failing tests describe the exact behavior your implementation must deliver. Make them pass.
2. **DO NOT modify any test file.** If a test seems wrong, return STATUS: NEEDS_CONTEXT with the specific concern; do not edit the test.
3. **DO NOT delete tests** to make them pass.
4. **DO NOT weaken assertions** by stubbing the function under test to return whatever the test expects without doing the real work — implement the actual behavior.
5. Write only the production code needed to satisfy the listed tests plus any plan requirements not yet covered by a test. Do not add features beyond the plan.
6. If a test in your list passes for the wrong reason (e.g. you discover the assertion would pass with an empty function), flag it in your report — the test reviewer in the next pipeline run will need to know.

## Instructions
1. Read all files you need to modify BEFORE making changes.
2. Implement exactly what the plan specifies for this work unit.
3. Follow existing code conventions in the project.
4. Add appropriate logging at decision points.
5. Do NOT write new tests — that phase is complete.
6. Do NOT run linters — that's a separate phase.
7. After implementation, list all files you created or modified and which tests you confirmed pass locally (if you ran any).

Be precise. Don't add features not in the plan. Don't refactor unrelated code.
```

**After each wave completes (all coders in the wave return), update `.mz/task/<task_name>/state.md` with:**

- `current_wave: N`
- Per-coder results: STATUS (`DONE` / `DONE_WITH_CONCERNS` / `BLOCKED` / `NEEDS_CONTEXT`) for each work unit
- Cumulative list of files modified (from `implementation.md` or each coder's artifact)

This state update is mandatory — it enables safe resumption if context is compacted between waves.

### 6.3 Collect results

After all waves complete, collect the list of all files modified/created across all coders.
Save implementation summary to `.mz/task/<task_name>/implementation.md`.
Update state file phase to `implementation_complete`.

**Test-tampering audit**: before proceeding to Phase 7, diff the test files against the Phase 3 / Phase 5 snapshot. If any test file in `.mz/task/<task_name>/tests.md` was modified during Phase 6, escalate via AskUserQuestion. The TDD contract is that coders implement against tests, never alter them. If the audit reveals an unavoidable test edit (e.g. a fixture parameter the plan missed), the user must explicitly approve before continuing.

______________________________________________________________________

## Phase 7: Code Review

**Goal**: Catch bugs, architecture issues, and missed requirements.

Set `code_review_iteration = 0`.

**Loop start:**

### 7.1 Review code

Spawn a `pipeline-code-reviewer` agent (model: **opus**) with:

```
Review the implementation of this task:
<task description>

Read the plan at .mz/task/<task_name>/plan.md.
Read the file list at .mz/task/<task_name>/implementation.md.
Read the test list at .mz/task/<task_name>/tests.md (these tests existed before the implementation — the implementation was written to satisfy them).

Review each modified production file for:
1. **Correctness** — Does it match the plan? Logic bugs? Off-by-one errors?
2. **Security** — OWASP top 10, input validation, injection risks
3. **Error handling** — Are errors caught and handled properly?
4. **Code quality** — Naming, structure, DRY, SOLID principles
5. **Completeness** — Is anything from the plan missing? Is anything in the plan untested?
6. **Integration** — Will changes work together? Any conflicts between work units?
7. **Tests-as-spec** — Does the implementation deliver real behavior, or did it satisfy tests by hardcoding the expected return values? Spot-check at least 3 tests against their target functions.

Read every production file that was modified. Do not skip any. Do NOT review test files in this pass — the test review already happened in Phase 4.

Output a structured review:
- **VERDICT**: PASS or FAIL
- **Critical Issues** (must fix): numbered list
- **Minor Issues** (should fix): numbered list
- **Notes**: observations that don't need changes
```

Save review to `.mz/task/<task_name>/code_review_<iteration>.md`.

### 7.2 Handle verdict

**If PASS**: proceed to Phase 8.

**If FAIL and code_review_iteration < 3**:

- Increment `code_review_iteration`
- Group critical issues by file/work-unit
- Spawn `pipeline-coder` agents in parallel to fix issues, giving each agent the specific issues for its files
- Each fix agent gets: the review feedback for its files, the plan for context, the failing-test list, and the instruction to fix ONLY the flagged issues. Restate the no-test-modification rule.
- **After each coder dispatch, check the coder's STATUS.** If the coder returns `BLOCKED`: break the review loop immediately. Escalate via AskUserQuestion with: the coder's blocker message, the review iteration count consumed, and the current review failure details. Do not continue iterating.
- Only proceed with the review loop on `DONE` or `DONE_WITH_CONCERNS`.
- **Go to Loop start**

**If FAIL and code_review_iteration >= 3**:

- Use AskUserQuestion to escalate with unresolved issues.

Update state file phase to `code_review_passed`.

______________________________________________________________________

## Phase 8: Lint, Format, and Verify GREEN

**Goal**: Ensure everything compiles, passes linting, and the **full test suite** is green — both the new tests and any pre-existing ones.

### 8.1 Detect project tooling

Read `.mz/task/<task_name>/tooling.md` (written during Phase 0 setup). If the file is absent (tooling was not detected at setup), dispatch `pipeline-tooling-detector` (model: **haiku**) now as a fallback:

```
Detect project tooling and write the result to:
output_path: .mz/task/<task_name>/tooling.md
```

If the fallback dispatch still fails (e.g., `pipeline-tooling-detector` returns `BLOCKED`), escalate via AskUserQuestion before proceeding to 8.2.

### 8.2 Run linters and formatters

Dispatch a `pipeline-lint-runner` agent (model: **haiku**):

```
Run linters and formatters for the project.
lint_command: <lint_command from tooling.md, or "none detected">
format_command: <format_command from tooling.md, or "none detected">
output_path: .mz/task/<task_name>/lint_results.md
```

Read `.mz/task/<task_name>/lint_results.md`.

If `STATUS: DONE_WITH_CONCERNS`: dispatch a `pipeline-coder` (model: **opus**) with the lint issues from `lint_results.md` to fix them directly. Re-dispatch `pipeline-lint-runner` to confirm clean.

### 8.3 Run the full test suite

Dispatch a `pipeline-test-runner` agent (model: **haiku**):

```
Run the project's full test suite to verify GREEN.
test_command: <test_command from tooling.md>
output_path: .mz/task/<task_name>/test_results.md
```

Read `.mz/task/<task_name>/test_results.md`.

**If STATUS: DONE**: green bar restored. Proceed to Phase 9.

**If STATUS: DONE_WITH_CONCERNS** (failures exist):

Set `green_iteration = 0`. Max iterations: `MAX_GREEN_ITERATIONS`.

- Extract the failed test list from `test_results.md`. Classify each:
  - **TDD test (from `.mz/task/<task_name>/tests.md`) failing** — implementation does not yet satisfy that test. Coder must finish the work; do NOT delete or weaken the test.
  - **Pre-existing test failing** — the implementation regressed something. Coder must adjust the implementation to stop breaking existing behavior. Pre-existing tests may not be modified to "make them pass" without explicit user approval.
- Increment `green_iteration`.
- Dispatch a `pipeline-coder` agent (model: **opus**) with the classified failure list. Reinforce: **no test modifications**.
- **Check coder STATUS.** If `BLOCKED`: break the loop, escalate via AskUserQuestion with the blocker details and the failing test list. Do not continue iterating.
- Re-dispatch `pipeline-test-runner` to re-run.
- **Check test-runner STATUS.** If `BLOCKED` (e.g., command not found, exit 127): break the loop, escalate via AskUserQuestion. Do not retry a permanently unavailable test command.
- Repeat up to `MAX_GREEN_ITERATIONS` iterations. If still failing after `MAX_GREEN_ITERATIONS` attempts, escalate via AskUserQuestion.

### 8.4 Re-run linters after fixes

If any code was changed during test fixes, re-dispatch `pipeline-lint-runner` to ensure nothing regressed:

```
Verify lint is still clean after test fixes.
lint_command: <lint_command from tooling.md, or "none detected">
format_command: <format_command from tooling.md, or "none detected">
output_path: .mz/task/<task_name>/lint_results_final.md
```

Update state file phase to `tests_passing`.

______________________________________________________________________

## Sub-agent status handling

Follow `skills/shared/agent-status-protocol.md` for the standard 4-status protocol (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Skill-specific overrides are noted inline above where applicable.
