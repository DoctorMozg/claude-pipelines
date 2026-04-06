# Phases 1-3: Assessment, Quick Fixes, Research

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

If ALL criteria now pass → skip to Phase 5 (Optimization). Read `phases/fix_review_and_finalize.md` and jump to Phase 5.

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

Proceed to Phase 4. Read `phases/fix_review_and_finalize.md`.
