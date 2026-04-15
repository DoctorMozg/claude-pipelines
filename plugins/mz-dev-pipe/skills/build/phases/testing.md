# Phases 5-7: Test Writing, Test Review, Lint & Test Run

Full detail for the testing phases of the build skill. Covers writing tests, reviewing them for coverage and quality in parallel, and finally running the project's linters, formatters, and test suite.

## Contents

- [Phase 5: Test Writing](#phase-5-test-writing)
- [Phase 6: Test Review](#phase-6-test-review)
  - 6.1 Parallel reviews (coverage + quality + code)
  - 6.2 Consolidate reviews
- [Phase 7: Lint, Format, and Test Run](#phase-7-lint-format-and-test-run)
  - 7.1 Detect project tooling
  - 7.2 Run linters and formatters
  - 7.3 Run tests
  - 7.4 Re-run linters after fixes

______________________________________________________________________

## Phase 5: Test Writing

**Goal**: Create comprehensive tests for the implementation.

### 5.1 Write tests

Spawn a `pipeline-test-writer` agent (model: **opus**) with:

```
Write tests for this implementation:

## Task
<task description>

## Context
Read the plan at .mz/task/<task_name>/plan.md (includes test strategy).
Read the file list at .mz/task/<task_name>/implementation.md.

## Instructions
1. Read all implemented files to understand what needs testing
2. Follow the project's existing test patterns and frameworks
3. Cover:
   - Happy path for each work unit
   - Edge cases identified in the plan
   - Error handling paths
   - Integration between work units (if applicable)
4. Use the project's existing test infrastructure (fixtures, helpers, etc.)
5. Each test should be independent and not rely on test execution order
6. Name tests descriptively — the name should explain what's being verified
7. Group tests by feature/work-unit in logical test classes or modules

List all test files created.
```

Save test file list to `.mz/task/<task_name>/tests.md`.

______________________________________________________________________

## Phase 6: Test Review

**Goal**: Ensure tests are comprehensive, high-quality, and actually validate the implementation.

Set `test_review_iteration = 0`.

**Loop start:**

### 6.1 Parallel reviews

Spawn THREE review agents **in parallel** (all model: **sonnet**):

**Agent A — Test Coverage Reviewer** (`pipeline-test-coverage-reviewer`):

```
Review test COVERAGE for this implementation:

## Task: <task description>

Read the plan at .mz/task/<task_name>/plan.md (focus on test strategy section).
Read the implementation file list at .mz/task/<task_name>/implementation.md.
Read the test file list at .mz/task/<task_name>/tests.md.

Then read all implemented code and all test files.

Evaluate:
1. Are all public functions/methods tested?
2. Are all code paths covered (branches, error paths)?
3. Are edge cases from the plan covered?
4. Are there missing scenarios that should be tested?
5. Is there integration test coverage for component interactions?

Output:
- **VERDICT**: PASS or FAIL
- **Coverage gaps**: specific functions/paths not tested
- **Missing scenarios**: test cases that should exist but don't
```

**Agent B — Test Quality Reviewer** (`pipeline-test-quality-reviewer`):

```
Review test QUALITY for this implementation:

## Task: <task description>

Read the test file list at .mz/task/<task_name>/tests.md, then read all test files.

Evaluate:
1. Are tests actually testing behavior (not implementation details)?
2. Are assertions meaningful (not just "assert True")?
3. Are test names descriptive?
4. Is there proper setup/teardown?
5. Are tests independent (no shared mutable state, no ordering dependency)?
6. Are mocks/stubs used appropriately (not over-mocking)?
7. Would these tests catch real regressions?

Output:
- **VERDICT**: PASS or FAIL
- **Quality issues**: specific problems in specific test files/functions
- **Suggestions**: improvements that aren't blockers
```

**Agent C — Test Code Reviewer** (`pipeline-code-reviewer`):

```
Review the TEST CODE (not the implementation) for quality:

## Task: <task description>

Read the test file list at .mz/task/<task_name>/tests.md, then read all test files.

Evaluate:
1. Code quality of the tests themselves
2. Proper use of the testing framework
3. No hardcoded values that should be constants/fixtures
4. No security issues in test code (leaked credentials, etc.)
5. Tests follow project conventions

Output:
- **VERDICT**: PASS or FAIL
- **Issues**: specific problems to fix
```

### 6.2 Consolidate reviews

Save all three reviews to `.mz/task/<task_name>/test_review_<iteration>.md`.

**If ALL three PASS**: proceed to Phase 7.

**If any FAIL and test_review_iteration < 3**:

- Increment `test_review_iteration`
- Consolidate all failure feedback into a single fix list
- Spawn a `pipeline-test-writer` agent (model: **opus**) with the consolidated feedback to fix the tests
- **Go to Loop start**

**If any FAIL and test_review_iteration >= 3**:

- Use AskUserQuestion to escalate.

Update state file phase to `test_review_passed`.

______________________________________________________________________

## Phase 7: Lint, Format, and Test Run

**Goal**: Ensure everything compiles, passes linting, and tests actually pass.

### 7.1 Detect project tooling

Dispatch a `pipeline-tooling-detector` agent (model: **haiku**):

```
Detect project tooling and write the result to:
output_path: .mz/task/<task_name>/tooling.md
```

Read `.mz/task/<task_name>/tooling.md` when done. Use the detected commands in the steps below.

### 7.2 Run linters and formatters

Dispatch a `pipeline-lint-runner` agent (model: **haiku**):

```
Run linters and formatters for the project.
lint_command: <lint_command from tooling.md, or "none detected">
format_command: <format_command from tooling.md, or "none detected">
output_path: .mz/task/<task_name>/lint_results.md
```

Read `.mz/task/<task_name>/lint_results.md`.

If `STATUS: DONE_WITH_CONCERNS`: dispatch a `pipeline-coder` (model: **opus**) with the lint issues from `lint_results.md` to fix them directly. Re-dispatch `pipeline-lint-runner` to confirm clean.

### 7.3 Run tests

Dispatch a `pipeline-test-runner` agent (model: **haiku**):

```
Run the project test suite.
test_command: <test_command from tooling.md>
output_path: .mz/task/<task_name>/test_results.md
```

Read `.mz/task/<task_name>/test_results.md`.

**If STATUS: DONE**: proceed to Phase 8.

**If STATUS: DONE_WITH_CONCERNS** (failures exist):

- Extract the failed test list from `test_results.md`
- Dispatch a `pipeline-coder` agent (model: **opus**) to fix the failing code or tests (use judgment on which needs fixing), providing the failed test details
- Re-dispatch `pipeline-test-runner` to re-run
- Repeat up to 3 iterations. If still failing after 3 attempts, escalate to user via AskUserQuestion

### 7.4 Re-run linters after fixes

If any code was changed during test fixes, re-dispatch `pipeline-lint-runner` to ensure nothing regressed:

```
Verify lint is still clean after test fixes.
lint_command: <lint_command from tooling.md, or "none detected">
format_command: <format_command from tooling.md, or "none detected">
output_path: .mz/task/<task_name>/lint_results_final.md
```

Update state file phase to `tests_passing`.
