# Phases 3-4: Exploratory Tests and Report

## Phase 3: Exploratory Tests

**Goal**: Write and run tests that definitively prove or disprove the hypothesis. Unlike regression tests (which pin known-correct behavior), exploratory tests are probes — they test what the code *actually does* against what it *should do* per the hypothesis.

### 3.1 Assess testability

Not every hypothesis is testable. Before dispatching, check:

- **Testable**: the hypothesis makes a specific claim about code behavior that can be asserted against (return values, state changes, side effects, exception types, ordering guarantees)
- **Partially testable**: some aspects can be tested, others require manual verification or production observation (e.g., performance under load, race conditions that need specific timing)
- **Not testable**: the hypothesis is too abstract, architectural, or requires infrastructure not available in the test environment

If **not testable**: skip to Phase 4 with a note. The report will rely on code analysis and domain research only.

If **partially testable**: write tests for the testable parts, note what can't be tested.

### 3.2 Design test strategy

From `analysis.md` (and `domain_research.md` if available), extract the testable assertions identified by the researcher(s). For each assertion, determine:

- What input or setup triggers the behavior
- What the correct behavior should be (from domain research or specification)
- What the hypothesis predicts the code actually does
- How to observe the result (return value, exception, state change, mock assertion)

### 3.3 Dispatch test writer

Dispatch a `pipeline-test-writer` agent (model: **opus**):

```
Write exploratory tests to prove or disprove a hypothesis about the codebase.

## Hypothesis
<the user's hypothesis>

## Analysis
Read .mz/task/<task_name>/analysis.md for evidence and testable assertions.
<if domain research exists>
Read .mz/task/<task_name>/domain_research.md for correct behavior per spec.
</if>

## Testable Assertions
<numbered list from analysis, with expected correct behavior>

## Instructions
1. Read existing tests to understand project test conventions (file naming, framework, fixtures, helpers, assertion style).
2. Write focused tests — one per testable assertion. Each test should:
   - Set up the specific condition the hypothesis targets
   - Exercise the code path in question
   - Assert the EXPECTED CORRECT behavior (not the buggy behavior)
   - Have a clear name: `test_<hypothesis_aspect>` or equivalent
   - Include a docstring: "Exploratory: <what this test verifies>"
3. Place tests in the appropriate test file following project conventions.
4. Tests must be self-contained — no manual setup beyond normal test fixtures.
5. If a test requires mocking external dependencies, mock at the boundary (HTTP client, DB connection), not internal functions.
6. Do NOT fix any production code. Only write tests.
7. Do NOT modify existing tests.

## Scope constraint
<scope file list if set, otherwise "standard test location for the project">

## Report
- Test file path and test names
- What each test asserts and which assertion it targets
- Any fixtures or helpers created
- Tests that couldn't be written and why
```

### 3.4 Run and verify tests

Dispatch a `pipeline-test-runner` agent (model: **haiku**):

```
Run the exploratory tests written in the previous step.
test_command: <test_command from .mz/task/<task_name>/tooling.md>
specific_files: <test files written by pipeline-test-writer>
output_path: .mz/task/<task_name>/test_runner_results.md
```

Read `.mz/task/<task_name>/test_runner_results.md` and interpret each result:

| Result     | Interpretation                                                                       |
| ---------- | ------------------------------------------------------------------------------------ |
| **Passes** | Code handles this case correctly — evidence AGAINST the hypothesis (for this aspect) |
| **Fails**  | Code does NOT handle this case correctly — evidence FOR the hypothesis               |
| **Errors** | Test is broken (import error, setup failure, etc.) — not evidence either way         |

**Handle errors**: if tests error out, re-dispatch `pipeline-test-writer` with the error output from the artifact. Max `MAX_TEST_RETRIES = 2` re-dispatches, then re-dispatch `pipeline-test-runner`.

**Handle conflicts**: if new tests cause existing tests to fail, dispatch a `pipeline-coder` (model: **opus**) to revert the conflicting test immediately. Note it in the report as "could not test without side effects."

### 3.5 Record test results

Save to `.mz/task/<task_name>/test_results.md`:

```markdown
# Exploratory Test Results

## Tests Written
### <test_name>
- **File**: <path>
- **Assertion**: <what it tests>
- **Result**: PASS / FAIL / ERROR / REVERTED
- **Output**: <key output lines>
- **Interpretation**: supports hypothesis / refutes hypothesis / inconclusive

## Summary
- Tests written: <N>
- Passing (refutes hypothesis): <N>
- Failing (supports hypothesis): <N>
- Errors (inconclusive): <N>
- Reverted (conflict): <N>
- Not testable: <N> — <reasons>

## Test Disposition
<keep / remove — see 3.6>
```

### 3.6 Test disposition

Decide what to do with the exploratory tests:

- **Tests that pass** (code is correct): keep them — they add coverage for edge cases.
- **Tests that fail** (bug confirmed): keep them — they serve as regression tests for a future fix. Mark them with `@pytest.mark.xfail`, `test.skip("known issue: <description>")`, or the project's equivalent expected-failure annotation.
- **Tests that errored and couldn't be fixed**: remove them.
- **Tests that were reverted**: already removed.

Update state phase to `tested`.

______________________________________________________________________

## Phase 4: Synthesis & Report

**Goal**: Consolidate all evidence into a verdict and write a comprehensive investigation report.

### 4.1 Determine verdict

Weigh all evidence:

| Verdict                 | Criteria                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| **Confirmed**           | Code analysis + tests show the suspected issue exists. Fix is needed.                    |
| **Disproved**           | Code analysis + tests show the code handles the case correctly. No issue found.          |
| **Inconclusive**        | Mixed evidence, untestable aspects, or insufficient information to make a determination. |
| **Partially confirmed** | Some aspects of the hypothesis are confirmed, others are disproved or unclear.           |

Confidence level:

- **High**: multiple independent evidence sources agree (code analysis + tests + domain research)
- **Medium**: evidence points one direction but with caveats (e.g., tests pass but domain research suggests edge cases not covered)
- **Low**: conflicting evidence or insufficient data

### 4.2 Generate report

Write to `.mz/reports/investigate_<YYYY_MM_DD>_<hypothesis_summary>.md`.

If a file with that name exists, append `_v2`, `_v3`, etc.

```markdown
# Investigation Report: <hypothesis summary>

**Date**: <YYYY-MM-DD>
**Verdict**: <confirmed / disproved / inconclusive / partially confirmed>
**Confidence**: <high / medium / low>

## Hypothesis
<original hypothesis as stated by the user>

## Code Analysis

### Evidence Supporting Hypothesis
- <file:line> — <explanation>

### Evidence Refuting Hypothesis
- <file:line> — <explanation>

### Ambiguous Evidence
- <file:line> — <explanation>

## Domain Research
<findings from domain research — omit section if no domain research was conducted>
- **Correct behavior per spec**: <description>
- **Code compliance**: <matches / violates / partially complies>
- **Sources**: <documentation links>

## Exploratory Tests

### Tests That Passed (code is correct)
- <test_name> — <what it verified>

### Tests That Failed (hypothesis supported)
- <test_name> — <what it found>

### Not Testable
- <aspects that couldn't be tested and why>

## Verdict Rationale
<detailed explanation of why the verdict was reached, citing specific evidence>

## Recommendations
<if confirmed>
- The issue should be fixed. Key files: <file:line references>
- Consider running `/debug <concise bug description>` to fix it with a regression test.
</if>
<if disproved>
- No action needed. The code correctly handles this case.
- Exploratory tests have been kept to prevent future regressions.
</if>
<if inconclusive>
- Additional investigation needed. Specific gaps: <what's missing>
- Suggested next steps: <manual testing, production monitoring, etc.>
</if>

## Tests Added
- <test file:name> — <disposition: kept / marked xfail / removed>

## Pipeline Stats
- **Research agents dispatched**: <N>
- **Domain research**: <yes — topics / no>
- **Exploratory tests written**: <N>
- **Test retries**: <N>
```

### 4.3 Present to user

Summarize the report directly. Include:

- Verdict and confidence in one sentence
- Key evidence (top 2-3 items)
- Tests added and their disposition
- Recommended next action (fix with `/debug`, monitor, or close)
- Link to the full report file

Update state status to `completed`.
