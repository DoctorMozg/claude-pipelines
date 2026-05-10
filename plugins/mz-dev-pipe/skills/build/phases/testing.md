# Phases 3-5: Test Writing (RED), Test Review, Verify RED

Full detail for the test-first phases of the build skill. Tests are written **before any production code exists**, reviewed for coverage and quality in parallel, then run against the empty implementation to confirm they fail (the RED bar). Implementation does not begin until RED is verified.

## Contents

- [Phase 3: Test Writing (RED)](#phase-3-test-writing-red)
- [Phase 4: Test Review](#phase-4-test-review)
  - 4.1 Parallel reviews (coverage + quality + code)
  - 4.2 Consolidate reviews
- [Phase 5: Verify RED](#phase-5-verify-red)
  - 5.1 Run the new tests
  - 5.2 Handle results
  - 5.3 Save RED snapshot

______________________________________________________________________

## Phase 3: Test Writing (RED)

**Goal**: Create comprehensive, behavior-driven tests for every work unit in the plan. The tests describe the contract the implementation must satisfy. They are written **before any production code is touched** and will fail until Phase 6 makes them pass.

### 3.1 Write tests

Spawn a `pipeline-test-writer` agent (model: **opus**) with:

```
Write tests for an implementation that does not yet exist (TDD / RED phase).

## Task
<task description>

## Context
Read the plan at .mz/task/<task_name>/plan.md (includes work units and the test strategy).
Read the research at .mz/task/<task_name>/research.md for codebase conventions.

## TDD Mode — Read carefully
The production code described by the plan has NOT been written. You are in the RED phase of red-green-refactor. Your job:

1. Write tests that describe the BEHAVIOR each work unit must deliver, drawn from the plan's work units, test strategy, edge cases, and verification criteria.
2. Tests will reference functions, classes, or modules that do not exist yet. That is expected.
3. Imports for not-yet-created modules are allowed — the test file may fail to import, fail to collect, or raise `NotImplementedError` / `AttributeError` / `ModuleNotFoundError` against missing symbols. Treat all of those as the RED bar.
4. Do NOT write any implementation code. Do NOT stub the production module just to make the import succeed. The coder phase will create the module.
5. Do NOT use mocks to fake the missing implementation into existence. A test that passes only because the production code is mocked out tests nothing.
6. Each test name must describe the behavior under test, not the function name being called.

## Instructions
1. Read existing test files to understand the project's test patterns, framework, fixtures, helpers, and naming conventions.
2. For each work unit in the plan, write tests covering:
   - Happy path
   - Boundary values and edge cases identified in the plan
   - Error handling paths
   - Integration with other work units (where applicable)
3. Use the project's existing test infrastructure (fixtures, helpers, factories).
4. Each test must be independent and not rely on test execution order.
5. Group tests by feature / work unit in logical test classes or modules.
6. Do NOT modify any production code. Do NOT modify pre-existing tests unless the plan explicitly calls for it.

## Report
List every test file created or modified, the work unit it covers, and the specific behaviors asserted. Note any test that intentionally crosses work-unit boundaries (integration tests).
```

Save test file list and behavior-coverage map to `.mz/task/<task_name>/tests.md`.

______________________________________________________________________

## Phase 4: Test Review

**Goal**: Ensure tests are comprehensive, high-quality, and actually validate the behavior the plan promises — before the coder ever sees them.

Set `test_review_iteration = 0`.

**Loop start:**

### 4.1 Parallel reviews

Spawn TWO review agents **in parallel** (both model: **sonnet**):

**Agent A — Test Reviewer** (`pipeline-test-reviewer` — combined coverage + quality):

```
Review test COVERAGE and QUALITY for a TDD-mode implementation.

## Task: <task description>

Read the plan at .mz/task/<task_name>/plan.md (focus on work units and test strategy).
Read the test file list at .mz/task/<task_name>/tests.md.
Then read all test files.

The production code does NOT exist yet. Evaluate coverage against the PLAN, not against any implementation.

## Coverage axis (Critical findings here block verdict):
1. Does every work unit in the plan have at least one test?
2. Are the test strategy's listed scenarios all covered?
3. Are edge cases from the plan covered?
4. Are error paths explicitly tested (not just happy path)?
5. Is there an integration-level test for every cross-unit interaction the plan calls out?
6. Are there public behaviors in the plan that no test exercises?

## Quality axis (Critical findings here block verdict):
1. Are tests asserting behavior (not implementation details that don't exist yet)?
2. Are assertions meaningful and specific (not "assert True", not just "no exception")?
3. Are test names descriptive of the behavior under test?
4. Is setup/teardown correct? Are tests independent and order-free?
5. Are mocks used only at boundaries (network, time, randomness)? Flag any test where the production-code-to-be is mocked out — that test cannot fail RED meaningfully.
6. Would these tests catch real regressions once the implementation exists?
7. Do any tests embed values that look like reverse-engineered implementation choices rather than required behavior?

Output the unified Test Review per the agent's Return Format (Coverage section + Quality section + single VERDICT line).
```

**Agent B — Test Code Reviewer** (`pipeline-code-reviewer`):

```
Review the TEST CODE itself for craftsmanship.

## Task: <task description>

Read the test file list at .mz/task/<task_name>/tests.md, then read all test files.

Evaluate:
1. Code quality of the tests themselves (readability, structure, DRY where appropriate)
2. Proper use of the testing framework (parametrization, fixtures, markers)
3. No hardcoded values that should be constants/fixtures
4. No security issues in test code (leaked credentials, network calls to real services)
5. Tests follow project conventions

Output:
- **VERDICT**: PASS or FAIL
- **Issues**: specific problems to fix
```

### 4.2 Consolidate reviews

Save both reviews to `.mz/task/<task_name>/test_review_<iteration>.md`.

**If BOTH PASS**: proceed to Phase 5.

**If either FAILs and test_review_iteration < 3**:

- Increment `test_review_iteration`
- Consolidate all failure feedback into a single fix list
- Spawn a `pipeline-test-writer` agent (model: **opus**) with the consolidated feedback to fix the tests. Reinforce: **still TDD mode — no production code, no mocking the missing implementation.**
- **Go to Loop start**

**If any FAIL and test_review_iteration >= 3**:

- Use AskUserQuestion to escalate.

Update state file phase to `test_review_passed`.

______________________________________________________________________

## Phase 5: Verify RED

**Goal**: Run the new tests against the empty implementation and confirm they fail. Tests that pass against zero production code are silently broken — they would not catch regressions later.

### 5.1 Detect tooling

Read `.mz/task/<task_name>/tooling.md` (written during Phase 0 setup). If absent, dispatch `pipeline-tooling-detector` (model: **haiku**) as a fallback. Use `<test_command>` from the result.

### 5.2 Run the new tests

Dispatch a `pipeline-test-runner` agent (model: **haiku**):

```
Run the new tests written in Phase 3 to verify they FAIL against the current code (no implementation exists yet).
test_command: <test_command from tooling.md>
specific_files: <list of test files from .mz/task/<task_name>/tests.md>
output_path: .mz/task/<task_name>/red_run.md
```

Read `.mz/task/<task_name>/red_run.md`.

### 5.3 Handle results

Set `red_iteration = 0`. Max iterations: `MAX_RED_ITERATIONS`.

Classify each test in the run output:

| Result                             | Interpretation                                                                          | Action                                          |
| ---------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Fails (assertion or exception)** | Correctly RED. Implementation does not exist yet.                                       | Good. Counts toward RED bar.                    |
| **Errors (import / collection)**   | Production module not present. Acceptable RED form.                                     | Good. Counts toward RED bar.                    |
| **Passes**                         | Test asserts something already true (e.g. `assert True`, mock-only, no real assertion). | **Broken test.** Add to "unexpected pass" list. |

**If the entire run failed to execute** (e.g. `STATUS: BLOCKED`, exit 127, missing test runner): escalate via AskUserQuestion. Do not retry a permanently unavailable test command.

**If every test failed or errored as expected**: save snapshot (5.4) and proceed to Phase 6.

**If any tests unexpectedly passed AND `red_iteration < MAX_RED_ITERATIONS`**:

- Increment `red_iteration`.
- Re-dispatch `pipeline-test-writer` (model: **opus**) with the unexpected-pass list and the instruction:

```
The following tests passed against zero implementation, which means they assert nothing meaningful:

<unexpected-pass list with test names and file paths>

Rewrite each of these tests so they assert the actual behavior the plan promises. Do not stub the production code. Do not weaken assertions. Re-run will verify they now FAIL.
```

- After the rewrite returns, jump back to 5.2.

**If `red_iteration >= MAX_RED_ITERATIONS` and tests still unexpectedly pass**: escalate via AskUserQuestion with the unexpected-pass list and plan excerpts. Do not proceed to Phase 6 — silently broken tests defeat the entire pipeline.

### 5.4 Save RED snapshot

Append to `.mz/task/<task_name>/tests.md`:

```markdown
## RED Snapshot

- **Run**: red_run.md
- **Tests**: <count>
- **Failed (expected)**: <count>
- **Errored (expected — module/import missing)**: <count>
- **Passed (unexpected — must be zero to proceed)**: 0
- **Iteration**: <red_iteration>
```

Update state file phase to `red_verified`.

______________________________________________________________________

## Sub-agent status handling

Follow `skills/shared/agent-status-protocol.md` for the standard 4-status protocol (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Skill-specific overrides are noted inline above where applicable.
