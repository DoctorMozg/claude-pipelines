---
name: polish-pipeline
description: Polishes existing code to meet specific completion criteria — runs tests, iterates fixes with review, optimizes code. Provide criteria as the argument.
argument-hint: <completion criteria — what must pass, what must be fixed, what must work>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Polishing Pipeline

You are an orchestrator that takes existing code and polishes it until it meets specific completion criteria. Unlike the dev-pipeline which builds from scratch, you work with what's already there — running tests, diagnosing failures, fixing issues, reviewing changes, and optimizing code.

## Input

- `$ARGUMENTS` — The completion criteria. This can be:
  - "All tests in test_foo.py must pass"
  - "Pre-commit hooks must pass on all changed files"
  - "The WebSocket reconnection must handle timeout correctly"
  - "Fix all failing tests and clean up the implementation"
  - Any combination of pass/fail criteria and behavioral requirements

If empty, ask the user what needs to be polished.

## Constants

- **MAX_FIX_ITERATIONS**: 5 — max code-test-review cycles before escalating
- **MAX_REVIEW_RETRIES**: 3 — max times a review can fail before escalating
- **TASK_DIR**: `.mz/task/` in the project root

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse criteria

Break the input into a checklist of discrete, verifiable criteria. Each criterion must be something you can check programmatically or by reading code.

Example input: "All tests pass, pre-commit clean, no debug prints in src/"
→ Criteria:

1. All tests in scope pass
1. Pre-commit hooks pass
1. No `print()` statements in `src/` (excluding intentional logging)

### 0.2 Derive task name

Short snake_case name (max 30 chars) from the criteria summary.

### 0.3 Create task directory and state

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Polish: <criteria summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Iteration**: 0
- **Criteria**:
  1. [ ] <criterion 1>
  2. [ ] <criterion 2>
  ...
```

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

______________________________________________________________________

## Phase 1: Initial Assessment

**Goal**: Understand current state — what passes, what fails, what needs fixing.

### 1.1 Run all checks

Execute each criterion's verification command in parallel where possible:

- **Tests**: detect test framework and run relevant tests
- **Linters**: run pre-commit or project linters
- **Custom checks**: grep, file existence, behavioral checks

Record results for each criterion: PASS or FAIL with details.

### 1.2 Triage

Categorize each failing criterion:

| Criterion   | Status    | Failure Type                                                 | Complexity                  |
| ----------- | --------- | ------------------------------------------------------------ | --------------------------- |
| <criterion> | PASS/FAIL | test_failure / lint_error / missing_feature / behavioral_bug | simple / moderate / complex |

**Simple**: formatting, unused import, typo — fix directly without subagent.
**Moderate**: logic bug, missing error handling — needs a coder agent.
**Complex**: architectural issue, missing feature, unclear requirement — needs research first.

### 1.3 Handle unclear criteria

If any criterion is ambiguous or you can't determine how to verify it:

Use AskUserQuestion:

```
I need clarification on these criteria:

1. "<ambiguous criterion>" — How should I verify this? What does "correct" look like?
```

Do NOT proceed with unclear criteria. Get clarity first.

### 1.4 Save assessment

Write `.mz/task/<task_name>/assessment.md` with the triage table, all test/lint output, and the verification commands for each criterion.

Update state phase to `assessed`.

______________________________________________________________________

## Phase 2: Quick Fixes

**Goal**: Handle all simple failures directly before entering the agent loop.

### 2.1 Apply simple fixes

For each **simple** failure, fix it directly (no agent needed):

- Run formatters (`ruff format`, `clang-format`, etc.)
- Fix unused imports
- Fix trivial lint errors
- Fix obvious typos

### 2.2 Re-run checks

After quick fixes, re-run all failing criteria checks.
Update the criteria checklist in state.md.

If ALL criteria now pass → skip to Phase 5 (Optimization).

______________________________________________________________________

## Phase 3: Research (if needed)

**Goal**: Gather context for moderate/complex failures.

Only enter this phase if there are **complex** failures OR if moderate failures involve code you don't understand.

### 3.1 Codebase exploration

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
I'm polishing existing code to meet these criteria:
<failing criteria with error details>

Explore the codebase to understand:
1. The architecture around the failing code
2. How similar issues are handled elsewhere in the project
3. What the failing tests expect and why they fail
4. Any patterns or conventions relevant to the fixes

Report:
- Root cause analysis for each failure
- Relevant files and their roles
- Suggested fix approaches
- Any risks or dependencies

Save nothing — just report findings.
```

### 3.2 Domain research (if complex failures involve external knowledge)

Spawn a second `pipeline-researcher` agent (model: **sonnet**) in parallel if needed:

```
Research external context for these issues:
<complex failure descriptions>

Focus on:
1. Correct behavior/API usage for the failing functionality
2. Known issues or gotchas
3. Best practices for the fix approach

Report concise, actionable findings.
```

### 3.3 Save research

Write findings to `.mz/task/<task_name>/research.md`.
Update state phase to `researched`.

______________________________________________________________________

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

## Instructions
1. Read the failing files and related code BEFORE making changes
2. Fix ONLY the specific issues listed — do not refactor or improve other code
3. Do not touch code unrelated to the failures
4. After fixing, list all files you modified

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

______________________________________________________________________

## Error Handling

- If a test framework isn't detected, ask the user how to run tests.
- If a criterion can't be verified programmatically, ask the user for a verification command.
- If research fails to identify root cause after 2 attempts, ask the user for context.
- Always save state before spawning agents.
- If a fix makes things worse (more criteria fail than before), revert the change immediately and try a different approach.

## State Management

After each phase/iteration, update `.mz/task/<task_name>/state.md` with:

- Current phase and iteration count
- Criteria checklist (checked/unchecked)
- Files modified so far
- Any escalation notes

Track cumulative file changes across iterations so the optimizer knows the full scope.
