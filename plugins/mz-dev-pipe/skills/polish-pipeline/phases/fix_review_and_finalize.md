# Phases 4-6: Fix Loop, Optimization, Final Verification

## Phase 4: Fix-Test-Review Loop

**Goal**: Iteratively fix failures, verify fixes, and review changes until all criteria pass.

Set `iteration = 0`.

**Loop start:**

### 4.1 Identify remaining failures

Re-run all criterion checks that are still failing.
Group failures by file/component for parallel fixing.

If no failures remain → proceed to Phase 5.

### 4.2 Fix

Determine fix strategy based on failure count and complexity:

**Few failures (1-3), concentrated in 1-2 files**: Fix directly using Edit tool — no agent needed.

**Multiple failures, spread across files**: Spawn `pipeline-coder` agents (model: **opus**) in parallel, one per file group:

```
You are fixing specific issues in existing code.

## Completion Criteria
<the overall criteria we're trying to meet>

## Your Failures to Fix
<specific test failures, lint errors, or behavioral issues for your files>

## Error Output
<actual test output, stack traces, lint messages>

## Research Context (if available)
Read .mz/task/<task_name>/research.md if it exists for root cause analysis.

## Scope constraint
<If scope was set, include: "You may ONLY edit files listed in .mz/task/<task_name>/scope_files.txt. If a fix requires editing a file outside this list, report it as a blocker instead of editing it.">
<If no scope: omit this section>

## Instructions
1. Read the failing files and related code BEFORE making changes
2. Fix ONLY the specific issues listed — do not refactor or improve other code
3. Do not touch code unrelated to the failures
4. If a scope constraint is set, do not edit files outside it
5. After fixing, list all files you modified

Focus on making the criteria pass. Nothing more.
```

### 4.3 Verify

Re-run ALL criterion checks (not just the ones you tried to fix — fixes can cause regressions).

Update criteria checklist in state.md.

### 4.4 Review changes

Spawn a `pipeline-code-reviewer` agent (model: **sonnet**) with:

```
Review the changes made in this polishing iteration.

## Goal
We are polishing code to meet these criteria:
<criteria list>

## Changes Made This Iteration
<git diff of changes since last iteration, or list of modified files>

Read all modified files. Review for:
1. Do the fixes actually address the failing criteria?
2. Did any fix introduce new bugs or regressions?
3. Are the fixes minimal and focused (no unnecessary changes)?
4. Do fixes follow existing code conventions?

Output:
- File-by-file analysis of changes
- Any new issues introduced
- Whether fixes are correct and safe

## VERDICT: PASS | FAIL
```

Save review to `.mz/task/<task_name>/review_<iteration>.md`.

### 4.5 Handle review result

**If review PASS AND all criteria PASS**: proceed to Phase 5.

**If review PASS AND some criteria still FAIL**:

- Increment `iteration`
- If `iteration < MAX_FIX_ITERATIONS` → **Go to Loop start**
- Else → escalate to user

**If review FAIL**:

- Spawn `pipeline-coder` agent(s) to fix review issues
- Re-run verification
- If review issues persist after `MAX_REVIEW_RETRIES` attempts → escalate to user

### 4.6 Escalation

Use AskUserQuestion:

```
After <N> fix iterations, these criteria still fail:
<failing criteria with latest error output>

Changes made so far:
<summary of what was tried>

Please provide guidance:
- Should I continue with a different approach?
- Is there context I'm missing?
- Should I skip certain criteria?
```

Update state phase to `fixes_complete` when all criteria pass and review passes.

______________________________________________________________________

## Phase 5: Optimization

**Goal**: Clean up the code — remove dead code, debug artifacts, and unnecessary complexity.

### 5.1 Optimize

Spawn a `pipeline-optimizer` agent (model: **opus**) with:

```
Optimize the code that was modified during this polishing task.

## Scope
Read .mz/task/<task_name>/state.md for the list of all files modified during this task.
Also check git diff to see all changes.

ONLY optimize files that were modified during this task. Do not touch other files.
<If scope was set: "Additionally, you may ONLY edit files listed in .mz/task/<task_name>/scope_files.txt. Even if you modified a file outside scope during a prior phase, do not optimize it.">

Work through your full optimization checklist:
1. Debug artifacts (print statements, commented-out code, TODOs)
2. Dead code (unused functions, unreachable blocks)
3. Unused imports
4. Code duplication (within the modified files only)
5. Unnecessary complexity
6. Consistency

Report all changes made.
```

### 5.2 Verify after optimization

Re-run ALL criterion checks to ensure optimization didn't break anything.

**If any criterion regressed**: revert the optimization that caused it (read the optimizer's report to identify which change broke things) and re-run checks.

### 5.3 Review optimization

Spawn a `pipeline-code-reviewer` agent (model: **sonnet**) with:

```
Review the optimization changes made to this code.

The code was functionally complete and passing all criteria before optimization.
Verify that optimizations:
1. Did not change any behavior
2. Are genuinely improvements (not just style preferences)
3. Didn't remove anything that's actually used

Read all modified files. Check each removal against grep results.

## VERDICT: PASS | FAIL
```

**If FAIL**: Spawn `pipeline-coder` to fix issues, re-run checks, re-review. Max 2 retries.

Update state phase to `optimized`.

______________________________________________________________________

## Phase 6: Final Verification

**Goal**: One last pass to confirm everything is clean.

### 6.1 Run all criteria checks

Execute every criterion verification one final time.

### 6.2 Run linters/formatters

Run the project's full lint and format suite to catch anything the optimization might have introduced.

### 6.3 Confirm completion

All criteria must be PASS. If any fail at this point, return to Phase 4 with `iteration` incremented.

### 6.4 Report

Write `.mz/task/<task_name>/summary.md`:

```markdown
# Polish Complete: <criteria summary>

## Criteria Status
- [x] <criterion 1> — PASS
- [x] <criterion 2> — PASS

## Changes Made
<list of all files modified with brief descriptions>

## Fix Iterations
<how many fix-test-review cycles were needed>

## Optimizations Applied
<summary from optimizer report>

## Key Decisions
<any non-obvious choices made during polishing>
```

Report to user: all criteria pass, here's what was done.

Update state to `completed`.
