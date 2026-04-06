# Phases 7-10: Parallel Review, Iteration, Regression Tests, and Finalization

Full detail for the review, rejection-handling, regression-testing, and finalization phases of the dev-review-and-fix skill. Covers dispatching mirrored reviewers per chunk, selective re-dispatch of rejected chunks, writing regression tests for critical/high severity fixes, and producing the final summary.

## Contents

- [Phase 7: Parallel Review](#phase-7-parallel-review)
  - 7.1 Dispatch reviewers
  - 7.2 Collect verdicts
- [Phase 8: Handle Verdicts](#phase-8-handle-verdicts)
  - 8.1 Decision tree
  - 8.2 Borderline verdicts
- [Phase 9: Regression Tests](#phase-9-regression-tests)
  - 9.1 Select findings for regression tests
  - 9.2 Dispatch test writers
  - 9.3 Verify new tests pass
- [Phase 10: Final Summary](#phase-10-final-summary)
  - 10.1 Final verification
  - 10.2 Write summary
  - 10.3 Report to user

______________________________________________________________________

## Phase 7: Parallel Review

**Goal**: Validate every chunk's fixes against the original findings AND the trivially-adjacent rule.

### 7.1 Dispatch reviewers

Spawn M = N `pipeline-code-reviewer` agents (model: **opus**) in a **single message** using parallel tool calls. One reviewer per chunk (1:1 mirror with coders).

Each reviewer's prompt:

```
Review the fixes applied to one chunk of a larger dev-review-and-fix pass.

## Chunk: <chunk name>

## Files modified in this chunk
<file list>

## Context
Read .mz/task/<task_name>/scope.md for the overall audit context.
Read .mz/task/<task_name>/findings.md for the full finding list.
Read .mz/task/<task_name>/chunks.md to confirm your chunk's scope.
Read .mz/task/<task_name>/fixes_<iteration>.md — specifically the section for this chunk — for what the coder claims to have done.
Read .mz/task/<task_name>/verify_<iteration>.md — the code is currently passing verification.

## Approved findings for this chunk
<list of findings F<ids> with descriptions>

## What to verify

### 1. Every approved finding is actually fixed
For each F<id> in your chunk's approved list:
- Read the modified code at file:line
- Confirm the fix actually addresses the described problem
- Confirm the fix uses a reasonable approach (doesn't need to match the proposed fix literally)
- Confirm no stub / TODO / pass-through fix

### 2. Trivial-adjacent fixes are genuinely trivial
For each TA<id> the coder reported:
- Verify it's in the SAME FUNCTION BODY as an approved fix
- Verify the bug is obvious (null check, typo, off-by-one, wrong variable)
- Verify no new imports / helpers / tests were needed
- Verify the change is ≤ 5 lines
- If ANY trivial-adjacent fix fails these criteria, the chunk FAILS — scope creep is a blocker.

### 3. No unauthorized changes
Read every modified file. For each change NOT listed in the coder report:
- Is it an acceptable consequence of a listed fix (e.g., renamed variable references)?
- Or is it scope creep?
If you find unauthorized changes, the chunk FAILS.

### 4. No new bugs introduced
Spot-check every fix for:
- Regressions to sibling code paths
- Broken invariants
- Missing error handling that existed before
- Changed behavior outside the intentional fix surface

### 5. Observed Additional Issues (informational)
The coder may have reported OA<ids> — things they saw but did not fix. These are informational only; do not penalize the chunk for them. Verify the coder correctly judged them as NOT trivially-adjacent (if they were, that's scope creep the coder should have fixed; if they weren't, the coder was right to defer).

Read every modified file in this chunk. Do not skip any.

Output:
- **VERDICT**: PASS or FAIL
- **Findings verified fixed**: list of F<ids> that pass your check
- **Findings NOT fixed**: list of F<ids> where the fix is incomplete or wrong
- **Trivial-adjacent check**: pass/fail per TA<id>
- **Unauthorized changes**: list or "none"
- **New bugs introduced**: list or "none"
- **Critical Issues** (must fix): numbered list with file:line references
- **Minor Issues** (should fix): numbered list
```

**Important**: reviewers only run for chunks that were touched in the current iteration. Chunks that passed in a prior iteration are frozen and not re-reviewed.

### 7.2 Collect verdicts

After all reviewers complete, merge into `.mz/task/<task_name>/review_<iteration>.md`:

```markdown
# Review (Iteration <N>)

## Chunk 1: <name> — PASS / FAIL
<reviewer output>

## Chunk 2: <name> — PASS / FAIL
...

## Summary
- Chunks reviewed this iteration: X
- Chunks PASSED: Y
- Chunks FAILED: Z
- Chunks frozen (previously approved): W
- Rejected chunks for next iteration: <list>
- Trivial-adjacent violations: <list, if any>
- Unauthorized changes flagged: <list, if any>
```

______________________________________________________________________

## Phase 8: Handle Verdicts

**Goal**: Decide whether to finalize, iterate, or escalate.

### 8.1 Decision tree

**If ALL chunks PASS** (including frozen ones from prior iterations):

- Update state file phase to `review_passed`
- Proceed to Phase 9

**If ANY chunk FAILS AND `review_iteration < MAX_REVIEW_ITERATIONS`**:

- Increment `review_iteration`
- Build a rejection list: chunk name + consolidated reviewer feedback for each failing chunk
- Go back to **Phase 5** — but dispatch coders ONLY for rejected chunks. Previously-approved chunks are frozen.
- Each rejected chunk's coder gets its specific reviewer feedback as input, plus its original findings list.
- After Phase 5 (re-fix), Phase 6 (re-verify), Phase 7 (re-review) run normally for the rejected chunks only.

**If ANY chunk FAILS AND `review_iteration == MAX_REVIEW_ITERATIONS`**:

- Escalate via AskUserQuestion:

```
After <N> review iterations, these chunks still fail review:

<chunk name>:
<unresolved reviewer feedback>

<another chunk>:
...

Options:
1. Revert the rejected chunks' changes entirely and finalize with only the approved chunks
2. Accept the rejected chunks as-is despite the reviewer feedback (NOT recommended)
3. Pause for manual investigation
```

### 8.2 Borderline verdicts

If a reviewer returns a PASS with significant "minor issues" that sound like real bugs, OR a FAIL where the critical issues look subjective (style preference, naming debate, etc.), **ask the user** via AskUserQuestion rather than auto-deciding.

Example:

```
Reviewer for chunk "<name>" returned a borderline verdict:

<reviewer output>

The critical issues look subjective rather than behavior-breaking. How should I proceed?
1. Treat as FAIL and iterate
2. Treat as PASS and proceed
3. Fix specific issues only (name them)
```

______________________________________________________________________

## Phase 9: Regression Tests

**Goal**: Pin the fixed behavior with regression tests for the most important fixes, so future changes can't silently reintroduce the bug.

### 9.1 Select findings for regression tests

From the approved findings that were successfully fixed and passed review, select those whose severity is in `REGRESSION_TEST_SEVERITIES = [critical, high]`.

Group the selected findings by affected file (same chunking logic as Phase 4). Schedule waves of ≤ `MAX_CODERS = 6`.

**If the selection is empty** (no critical or high findings were fixed): skip Phase 9 entirely and proceed to Phase 10.

Write `.mz/task/<task_name>/regression_test_plan.md`:

```markdown
# Regression Test Plan
- Findings eligible: <list of F<ids> with severity critical or high>
- Chunks: <list, by file>
- Waves: <count>
```

### 9.2 Dispatch test writers

For each wave, spawn `pipeline-test-writer` agents (model: **opus**) in a **single message**, one per chunk.

Each test writer's prompt:

```
Write regression tests that pin the behavior of recently-fixed bugs.

## Chunk: <chunk name>

## Files fixed in this chunk
<file list — the fixes are already applied>

## Findings being pinned
For each finding below, write a test that would have caught the original bug:

### F<id> — <file:line> — severity: <level>
- **Original problem**: <from findings.md>
- **Fix applied**: <from fixes_<iteration>.md>

### F<id> — ...

## Context
Read .mz/task/<task_name>/findings.md for finding details.
Read .mz/task/<task_name>/fixes_<final_iteration>.md for the fix reports.
Read the current (post-fix) files — the fixes are already in place.

## Instructions
1. Follow the project's existing test patterns (detect the test framework, fixtures, naming).
2. For each finding, write ONE focused test (not a test suite). The test should:
   - Exercise the code path that contained the bug
   - Assert the NOW-CORRECT behavior that the fix established
   - PASS against the current (fixed) code
   - Have a name that makes the intent clear (e.g., `test_parse_empty_input_does_not_crash` for a null-handling fix)
   - Include a docstring/comment explaining what pre-fix behavior it pins, e.g.:
     "Regression test for F7: before the fix, calling parse('') raised IndexError.
     After the fix, it returns an empty result."
3. Do NOT modify implementation files.
4. Do NOT add tests for findings not in your assigned list.
5. Do NOT refactor existing tests.
6. If a finding genuinely cannot be tested (e.g., affects a bootstrap path with no test harness), report that instead of inventing a contrived test.

## Output
List all test files created or modified, and for each, which F<id> each new test pins.
```

### 9.3 Verify new tests pass

After all test writers complete, run the project's test suite. All newly-added tests must pass. Lint must still be clean.

**If any new test fails**: do NOT auto-fix. Escalate via AskUserQuestion:

```
A regression test just added is failing on the current (fixed) code:

Failing test: <test name>
File: <test file>
Finding pinned: F<id>

This may indicate:
- The regression test is wrong (test writer misunderstood the fix)
- The fix is incomplete (doesn't actually fix the bug the test is asserting)

Please investigate.
```

Do not auto-delete the failing test or auto-revert anything — a failing regression test is a signal, not noise.

**If lint regressed from the test additions**: dispatch `pipeline-coder` to fix the lint issues in the new test files only. Max 1 attempt, then escalate.

Write `.mz/task/<task_name>/regression_tests.md`:

```markdown
# Regression Tests Added

## Tests written
### F<id> — <test file>:<test name>
- Pins: <one-line summary of what the test asserts>
- Status: PASS

### F<id> — ...

## Tests not written (couldn't be pinned)
- F<id>: <reason from test writer>

## Summary
- Tests added: N
- Findings covered: M of <total critical + high>
```

Update state file phase to `regression_tests_added`.

______________________________________________________________________

## Phase 10: Final Summary

**Goal**: Record what happened and report to the user.

### 10.1 Final verification

Run tests and linters one last time. Confirm:

- All originally-passing tests still pass
- All new regression tests pass
- Lint is at or below the pre-fix baseline

If any regression appears at this stage (should not, since Phase 6 ran per iteration), escalate to the user.

### 10.2 Write summary

Write `.mz/task/<task_name>/summary.md`:

```markdown
# dev-review-and-fix Summary

**Argument**: <original argument or "roam">
**Task directory**: .mz/task/<task_name>/
**Completed**: <timestamp>

## Audit Overview
- Scope: <roam / narrowed>
- Files scanned: N
- Lenses run: <list>
- Total findings located (before caps): <raw count>
- Findings in fix plan (after caps): <count>
- Findings skipped by caps: <breakdown by severity>

## Fix Outcome
- Chunks: C
- Waves: W
- Review iterations: R
- Fix-loop attempts: F
- Findings fixed: <count, by severity>
- Findings reverted / escalated: <count, if any>

## Fixes Applied
### Critical
#### F<id> — <file:line>
- Description: <one line>
- Fix: <one line from coder report>
- Regression test: <test file / "not added">

#### F<id> — ...

### High (top 10 of <total>)
...

### Medium (top 5 of <total>)
...

## Trivial Adjacent Fixes
<list of TA<ids> with file:line and one-line description>

## Observed Additional Issues (deferred)
Observations from coders that did not qualify as trivially-adjacent fixes:
- OA<id>: <file:line> — <description>

## Deferred Findings (not in this pass)
- <count> high findings below the cap
- <count> medium findings below the cap
- <count> low findings (never included)

Consider running dev-review-and-fix again with lens-specific focus to address these.

## Regression Tests Added
- Total: N
- Coverage: M of <total critical + high>
- Gaps: <findings that couldn't be pinned with tests>

## Key Decisions
<any non-obvious choices made during the run, especially user clarifications from AskUserQuestion prompts>
```

### 10.3 Report to user

Display:

- Path to `summary.md`
- Headline: "Fixed X findings (N critical, M high, P medium) across C files in W waves. R review iterations needed."
- Deferred counts (below-cap + low severity) as a follow-up opportunity
- Regression test coverage ("Added N regression tests covering M of <total> critical+high findings")
- Any escalations or unresolved items

Update state file status to `completed`.
