# Phases 3-6: Regression Test, Fix, Verify, and Report

## Phase 3: Regression Test (TDD)

**Goal**: Write a single test that captures the bug — it must FAIL against the current (buggy) code. The fix in Phase 4 will make it pass.

### 3.1 Dispatch test writer

Dispatch a `pipeline-test-writer` agent (model: **opus**):

```
Write a regression test for a confirmed bug. The test must FAIL against the current code.

## Bug
Read .mz/task/<task_name>/diagnosis.md for root cause and proposed fix.
Read .mz/task/<task_name>/reproduction.md for how the bug manifests.

## Instructions
1. Read existing tests to understand the project's test conventions (file naming, framework, fixtures, helpers, assertion style).
2. Write ONE focused test that:
   - Exercises the exact code path where the bug occurs
   - Asserts the CORRECT behavior (which doesn't exist yet — so the test will fail)
   - Has a clear name: `test_<bug_description>_regression` or equivalent for the project's naming convention
   - Includes a docstring: "Regression test: <one-line bug description>"
3. Place the test in the appropriate test file following project conventions. If no existing test file covers this module, create one following the project's test directory structure.
4. The test must be self-contained — no manual setup required beyond normal test fixtures.
5. Do NOT fix the bug. Only write the test.
6. Do NOT modify any non-test files.

## Scope constraint
<scope file list if scope parameter was set, otherwise "all project files eligible">

## Report
- Test file path and test name
- What the test asserts (expected correct behavior)
- Why it will fail against current code
- Any test fixtures or helpers you created
```

### 3.2 Verify test fails

Dispatch a `pipeline-test-runner` agent (model: **haiku**):

```
Run the new regression test to verify it fails against the current (buggy) code.
test_command: <test_command from .mz/task/<task_name>/tooling.md>
specific_files: <regression test file from 3.1>
output_path: .mz/task/<task_name>/regression_run_initial.md
```

Read `.mz/task/<task_name>/regression_run_initial.md` and check each test result:

| Result                        | Action                                                                                                    |
| ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Fails (expected)**          | The test correctly captures the bug. Save to `regression_test.md`, proceed to Phase 4.                    |
| **Passes (unexpected)**       | Bug may already be fixed, or test doesn't exercise the right path. Re-dispatch test writer with feedback. |
| **Error (import/syntax/etc)** | Test is broken. Re-dispatch test writer with the error output from the artifact.                          |

**Retry limit**: 2 re-dispatches. If the test still doesn't fail correctly after 2 retries, escalate via AskUserQuestion:

```
The regression test could not be made to fail against the current code after <N> attempts.

Test: <test file:name>
Expected: test should FAIL (asserting correct behavior that doesn't exist)
Actual: <passes / errors>

This might mean:
1. The bug isn't reproducible via this test path
2. The bug was already fixed
3. The test doesn't exercise the right code path

How should I proceed?
```

### 3.3 Save regression test info

Write `.mz/task/<task_name>/regression_test.md`:

```markdown
# Regression Test

## Test
- **File**: <path>
- **Name**: <test function name>
- **Asserts**: <what correct behavior it checks>

## Current Result
- **Status**: FAILS (as expected)
- **Output**: <failure output summary>

## Notes
<any test fixtures or helpers created>
```

Update state phase to `test_written`.

______________________________________________________________________

## Phase 4: Fix

**Goal**: Apply the minimal fix to make the regression test pass without breaking anything else.

### 4.1 Dispatch coder

Regardless of fix complexity, dispatch a `pipeline-coder` agent with the diagnosis context and a minimal-fix constraint. Do not apply fixes directly in the orchestrator — orchestrators only route, they never write code.

### 4.2 Apply fix

Dispatch a `pipeline-coder` agent (model: **opus**):

```
Fix a diagnosed bug. A regression test already exists and must pass after your fix.

## Diagnosis
Read .mz/task/<task_name>/diagnosis.md for root cause and proposed fix.
Read .mz/task/<task_name>/regression_test.md for the test that must pass.

## Scope constraint
<scope file list if set, otherwise "all project files eligible">

## Instructions
1. Read the diagnosed root cause file(s) before making changes.
2. Apply the MINIMAL fix — fewest lines changed to resolve the root cause.
3. Do NOT refactor surrounding code, add features, or fix other bugs.
4. Do NOT modify the regression test.
5. Do NOT add new dependencies unless the diagnosis explicitly requires it.
6. The regression test must PASS after your fix.

## Report
- Files modified with description of changes
- Why this fix addresses the root cause
- Any concerns about the change
```

### 4.3 Verify fix

Dispatch a `pipeline-test-runner` agent (model: **haiku**) to run the regression test:

```
Run the regression test to verify the fix.
test_command: <test_command from .mz/task/<task_name>/tooling.md>
specific_files: <regression test file from regression_test.md>
output_path: .mz/task/<task_name>/regression_run_after_fix.md
```

Read `regression_run_after_fix.md`:

- **All pass**: good. Run the full suite.
- **Any fail**: fix didn't work. Iterate (4.4).

Dispatch a second `pipeline-test-runner` for the full suite:

```
Run the full test suite to check for regressions.
test_command: <test_command from .mz/task/<task_name>/tooling.md>
output_path: .mz/task/<task_name>/full_suite_after_fix.md
```

Read `full_suite_after_fix.md`:

- **STATUS: DONE**: no regressions. Proceed to Phase 5.
- **STATUS: DONE_WITH_CONCERNS**: fix introduced new failures. Iterate (4.4).

### 4.4 Fix iteration loop

Initialize `fix_iteration = 0` BEFORE the loop begins. Max iterations: `MAX_FIX_ITERATIONS = 3`.

On each iteration:

1. Increment `fix_iteration` at the START of the iteration (before dispatching the coder).
1. Analyze what went wrong: read failing test output, compare to diagnosis.
1. If regression test still fails: the fix is insufficient. Re-dispatch coder with the failure output and previous attempt context.
1. If regression test passes but other tests regress: the fix is too broad. Re-dispatch coder with regression details and instruction to narrow the change.
1. After the coder dispatch, check the coder's STATUS:
   - If `BLOCKED`: break the loop immediately. Do not run verification. Escalate via AskUserQuestion with the blocker message, the number of iterations consumed (`fix_iteration`), and the still-failing test output.
   - Only proceed to verification when STATUS is `DONE` or `DONE_WITH_CONCERNS`.
1. Re-run verification (4.3).

If `fix_iteration >= MAX_FIX_ITERATIONS` and still failing, escalate via AskUserQuestion:

```
The fix could not be stabilized after <N> iterations.

## Regression test
<status — passing or failing>

## Remaining failures
<test output>

## Attempts made
<summary of each iteration's approach>

Options:
1. Revert all fix changes and investigate manually
2. Accept partial fix (regression test passes but some tests regress)
3. Try a fundamentally different fix approach
```

Update state: increment `Fix iterations`, update phase to `fixed`.

______________________________________________________________________

## Phase 5: Verify & Review

**Goal**: Full verification pass, then independent code review of the fix and test.

### 5.1 Full verification

Dispatch `pipeline-test-runner` and `pipeline-lint-runner` in parallel (single message, two agent calls):

```
Run the full test suite for final verification.
test_command: <test_command from .mz/task/<task_name>/tooling.md>
output_path: .mz/task/<task_name>/final_test_results.md
```

```
Run linters for final verification.
lint_command: <lint_command from .mz/task/<task_name>/tooling.md, or "none detected">
format_command: <format_command from .mz/task/<task_name>/tooling.md, or "none detected">
output_path: .mz/task/<task_name>/final_lint_results.md
```

Read both artifacts. All must pass (or match pre-existing failure state). If anything new fails, return to Phase 4 for another fix iteration.

### 5.2 Code review

Dispatch a `pipeline-code-reviewer` agent (model: **opus**):

```
Review a bug fix and its regression test.

## Context
Read .mz/task/<task_name>/diagnosis.md for the root cause.
Read .mz/task/<task_name>/regression_test.md for the test.
Read .mz/task/<task_name>/reproduction.md for the bug reproduction.

Run `git diff HEAD` to see all changes made.

## Review Criteria
1. **Root cause alignment**: Does the fix actually address the diagnosed root cause, not just the symptom?
2. **Minimality**: Is this the smallest change that fixes the bug? Flag any unnecessary modifications.
3. **Regression test quality**: Does the test genuinely capture the bug? Would it catch a reintroduction?
4. **Convention compliance**: Do the fix and test follow project coding conventions?
5. **Side effects**: Could this fix change behavior in unintended ways?
6. **Similar patterns**: Are there other locations with the same bug pattern? (Report but don't require fixing.)

## Verdict
PASS — fix is correct, minimal, and well-tested.
FAIL — with specific issues that must be addressed.
```

### 5.3 Handle review verdict

| Verdict  | Action                                                                               |
| -------- | ------------------------------------------------------------------------------------ |
| **PASS** | Proceed to Phase 6.                                                                  |
| **FAIL** | Dispatch `pipeline-coder` (opus) with reviewer feedback. Re-verify (5.1). Re-review. |

**Retry limit**: `MAX_REVIEW_RETRIES = 2`. If the review still fails after 2 retries, escalate via AskUserQuestion with the reviewer's feedback and ask the user how to proceed.

Update state phase to `reviewed`.

______________________________________________________________________

## Sub-agent status handling

Follow `skills/shared/agent-status-protocol.md` for the standard 4-status protocol (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Skill-specific overrides are noted inline above where applicable.

______________________________________________________________________

## Phase 6: Report

**Goal**: Write a comprehensive debug report summarizing the investigation and fix.

### 6.1 Generate report

Write to `.mz/reports/debug_<YYYY_MM_DD>_<bug_summary>.md`.

If a file with that name exists, append `_v2`, `_v3`, etc.

```markdown
# Debug Report: <bug summary>

**Date**: <YYYY-MM-DD>
**Status**: fixed

## Bug Report
<original bug description / issue content>

## Reproduction
- **Method**: <test name / command / static analysis>
- **Result**: <reproduced / static confirmation>
- **Output**: <key failure output>

## Root Cause
<file:line — what was wrong and why>

## External Context
<domain research findings — omit section if no external deps were involved>

## Regression Test
- **File**: <path>
- **Test**: <test function name>
- **Asserts**: <what correct behavior it verifies>

## Fix
- **Files modified**: <list with brief description of each change>
- **Approach**: <what was changed and why>
- **Risk**: <low / medium / high>

## Verification
- **Tests**: <pass count / total — any pre-existing failures noted>
- **Lint**: <clean / warnings count>
- **Type check**: <clean / errors count, if applicable>

## Similar Patterns
<other locations with the same bug pattern, noted by reviewer — not fixed>

## Pipeline Stats
- **Fix iterations**: <N>
- **Review retries**: <N>
- **Domain research**: <yes — topic / no>
```

### 6.2 Present to user

Summarize the report to the user directly (not via AskUserQuestion). Include:

- Root cause in one sentence
- What was fixed (files and approach)
- Regression test location
- Similar patterns found (if any) as follow-up suggestions
- Link to the full report file

Update state status to `completed`.
