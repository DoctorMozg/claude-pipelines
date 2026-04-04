---
name: dev-pipeline
description: Full autonomous development pipeline — research, plan, code, review, test — with multi-agent orchestration. Provide a task description as the argument.
argument-hint: <task description>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Development Pipeline

You are an orchestrator that drives a full development lifecycle using specialized sub-agents.
You receive a task description and autonomously research, plan, implement, review, and test it.

## Input

- `$ARGUMENTS` — The task description. If empty, ask the user what they want built.

## Constants

- **MAX_REVIEW_ITERATIONS**: 3 — max times any review loop retries before escalating to user
- **TASK_DIR**: `.mz/task/` in the project root — all artifacts are saved here under a task-specific subdirectory

## Phase Overview

```
┌─────────┐    ┌──────┐    ┌─────────────┐    ┌──────────┐    ┌──────┐
│ Research │───▶│ Plan │───▶│ Plan Review │───▶│ Approval │───▶│ Code │
└─────────┘    └──────┘    │  (loop ≤3)  │    │  (user)  │    │(par) │
                           └─────────────┘    └──────────┘    └──┬───┘
                                                                 │
┌──────────────┐    ┌──────────┐    ┌─────────────┐             │
│ Completeness │◀───│ Optimize │◀───│ Final Code  │             │
│   Check      │    │          │    │   Review    │             │
└──────┬───────┘    └──────────┘    └──────┬──────┘             │
       │                                   │                    │
       │              ┌─────────────┐    ┌─┴───────────┐  ┌────▼───────┐
       │              │ Test Review │◀───│ Lint & Test │◀─│Code Review │
       │              │ (parallel)  │    │    Run      │  │ (loop ≤3)  │
       │              │ (loop ≤3)   │───▶└─────────────┘  └────────────┘
       │              └─────────────┘
       │ FAIL: restart from appropriate phase
       │ PASS: done
       ▼
     DONE
```

______________________________________________________________________

## Phase 0: Setup

### 0.1 Derive task name

From the task description, derive a short snake_case name (max 30 chars) for the task directory.
Example: "Add WebSocket support for real-time updates" → `add_websocket_realtime`

### 0.2 Create task directory

```bash
mkdir -p .mz/task/<task_name>
```

### 0.3 Initialize state file

Write `.mz/task/<task_name>/state.md` with:

```markdown
# Task: <task description>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Iterations**: 0
```

### 0.4 Create task tracking

Use TaskCreate to create a top-level task for each pipeline phase so the user can see progress.

______________________________________________________________________

## Phase 1: Research

**Goal**: Gather context about the codebase and domain to inform planning.

### 1.1 Codebase exploration

Spawn a `pipeline-researcher` agent (model: **sonnet**) with:

```
Explore the codebase to understand the context for this task:
<task description>

Focus on:
1. Project structure, key directories, entry points
2. Existing patterns, conventions, and architecture relevant to the task
3. Files that will likely need modification
4. Existing tests and how they're structured
5. Build system, lint commands, test commands
6. Reusable components and utilities

Report structured findings per the agent's output format.
Save nothing — just report findings.
```

### 1.2 Domain research (if needed)

If the task involves external APIs, protocols, libraries, or domain knowledge that isn't obvious from the codebase, spawn a second `pipeline-researcher` agent (model: **sonnet**) with:

```
Research the external domain knowledge needed for this task:
<task description>

Use WebSearch and WebFetch to find:
1. Best practices and common patterns
2. API documentation or protocol specs if applicable
3. Known pitfalls and edge cases
4. Security considerations
5. Performance implications

Report concise, actionable findings. No fluff.
```

Run 1.1 and 1.2 **in parallel** if both are needed.

### 1.3 Save research

Write combined findings to `.mz/task/<task_name>/research.md`.
Update state file phase to `research_complete`.

______________________________________________________________________

## Phase 2: Planning

**Goal**: Create a detailed, actionable implementation plan.

### 2.1 Generate plan

Spawn a `pipeline-planner` agent (model: **opus**) with:

```
You are planning the implementation of this task:
<task description>

Read the research file at .mz/task/<task_name>/research.md for codebase and domain context.

Create a detailed implementation plan with:

1. **Summary** — What we're building and why
2. **Work Units** — Break the implementation into independent, parallelizable units where possible. Each unit should specify:
   - Files to create or modify (with paths)
   - What changes to make (specific enough for a developer to implement without guessing)
   - Dependencies on other work units (if any)
3. **Test Strategy** — What tests to write, what to cover, edge cases
4. **Risk Assessment** — What could go wrong, what to watch out for
5. **Verification Criteria** — How we know the task is truly complete

Mark each work unit as either PARALLEL (can run simultaneously with others) or SEQUENTIAL (depends on prior units).
Be specific about file paths and function signatures. Vague plans waste time.
```

Save output to `.mz/task/<task_name>/plan.md`.

### 2.2 Plan review loop

Set `plan_iteration = 0`.

**Loop start:**

Spawn a `pipeline-plan-reviewer` agent (model: **sonnet**) with:

```
Review this implementation plan for the task: <task description>

Read the plan at .mz/task/<task_name>/plan.md and the research at .mz/task/<task_name>/research.md.

Evaluate:
1. **Completeness** — Does it cover all aspects of the task? Missing pieces?
2. **Correctness** — Are the proposed changes technically sound?
3. **Architecture** — Does it fit the existing codebase patterns? Any anti-patterns?
4. **Parallelizability** — Are work units properly split for parallel execution?
5. **Testability** — Is the test strategy comprehensive? Missing edge cases?
6. **Risk** — Are risks properly identified? Missing any?

Output a structured review:
- **VERDICT**: PASS or FAIL
- **Issues** (if FAIL): numbered list of specific issues to fix
- **Suggestions** (optional): improvements that aren't blockers
```

Save review to `.mz/task/<task_name>/plan_review_<iteration>.md`.

**If PASS**: proceed to Phase 2.3.

**If FAIL and plan_iteration < 3**:

- Increment `plan_iteration`
- Spawn a new `pipeline-planner` agent (model: **opus**) with the original task, research, current plan, AND the review feedback. Ask it to revise the plan addressing all issues.
- Save revised plan to `.mz/task/<task_name>/plan.md` (overwrite)
- **Go to Loop start**

**If FAIL and plan_iteration >= 3**:

- Use AskUserQuestion to escalate: "Plan failed review 3 times. Here are the unresolved issues: <issues>. Please provide guidance."
- Incorporate user guidance and create a final plan revision.

### 2.3 User approval

Use AskUserQuestion to present the final plan to the user:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Reply 'approve' to proceed, or provide feedback for changes.
```

If the user provides feedback instead of approving, revise the plan accordingly (spawn `pipeline-planner` agent again with feedback) and re-present. Do NOT re-run the review loop — the user's word is final.

Update state file phase to `plan_approved`.

______________________________________________________________________

## Phase 3: Implementation

**Goal**: Implement the plan using parallel coders where possible.

### 3.1 Parse work units

From the approved plan, extract all work units. Group them into execution waves:

- **Wave 1**: All units marked PARALLEL with no dependencies
- **Wave 2**: Units that depend on Wave 1 outputs
- **Wave N**: Continue until all units scheduled

### 3.2 Execute waves

For each wave, spawn **one agent per work unit** in parallel.

Use `pipeline-coder` agent type for all work units. Model: **opus** for all coders.

Each coder agent prompt:

```
You are implementing one work unit of a larger task.

## Overall Task
<task description>

## Plan
Read the full plan at .mz/task/<task_name>/plan.md for context.

## Your Work Unit
<specific work unit details>

## Instructions
1. Read all files you need to modify BEFORE making changes
2. Implement exactly what the plan specifies for this work unit
3. Follow existing code conventions in the project
4. Add appropriate logging at decision points
5. Do NOT write tests — that's a separate phase
6. Do NOT run linters — that's a separate phase
7. After implementation, list all files you created or modified

Be precise. Don't add features not in the plan. Don't refactor unrelated code.
```

### 3.3 Collect results

After all waves complete, collect the list of all files modified/created across all coders.
Save implementation summary to `.mz/task/<task_name>/implementation.md`.
Update state file phase to `implementation_complete`.

______________________________________________________________________

## Phase 4: Code Review

**Goal**: Catch bugs, architecture issues, and missed requirements.

Set `code_review_iteration = 0`.

**Loop start:**

### 4.1 Review code

Spawn a `pipeline-code-reviewer` agent (model: **opus**) with:

```
Review the implementation of this task:
<task description>

Read the plan at .mz/task/<task_name>/plan.md.
Read the file list at .mz/task/<task_name>/implementation.md.

Review each modified file for:
1. **Correctness** — Does it match the plan? Logic bugs? Off-by-one errors?
2. **Security** — OWASP top 10, input validation, injection risks
3. **Error handling** — Are errors caught and handled properly?
4. **Code quality** — Naming, structure, DRY, SOLID principles
5. **Completeness** — Is anything from the plan missing?
6. **Integration** — Will changes work together? Any conflicts between work units?

Read every file that was modified. Do not skip any.

Output a structured review:
- **VERDICT**: PASS or FAIL
- **Critical Issues** (must fix): numbered list
- **Minor Issues** (should fix): numbered list
- **Notes**: observations that don't need changes
```

Save review to `.mz/task/<task_name>/code_review_<iteration>.md`.

### 4.2 Handle verdict

**If PASS**: proceed to Phase 5.

**If FAIL and code_review_iteration < 3**:

- Increment `code_review_iteration`
- Group critical issues by file/work-unit
- Spawn `pipeline-coder` agents in parallel to fix issues, giving each agent the specific issues for its files
- Each fix agent gets: the review feedback for its files, the plan for context, and instructions to fix ONLY the flagged issues
- **Go to Loop start**

**If FAIL and code_review_iteration >= 3**:

- Use AskUserQuestion to escalate with unresolved issues.

Update state file phase to `code_review_passed`.

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

Examine the project for available tools:

- Look for `pyproject.toml`, `.pre-commit-config.yaml`, `Makefile`, `package.json`, `.clang-format`
- Determine the correct lint, format, and test commands

### 7.2 Run linters and formatters

Run the project's linting and formatting tools. Common patterns:

```bash
# If pre-commit exists
pre-commit run --from-ref origin/$(git symbolic-ref refs/remotes/origin/HEAD --short | sed 's|origin/||') --to-ref HEAD

# If package.json with lint script
npm run lint

# If pyproject.toml with ruff
ruff check . --fix
ruff format .
```

Fix any issues found. If fixes require code changes, make them directly (simple formatting fixes don't need a coder agent).

### 7.3 Run tests

Run the project's test suite for the files you created:

```bash
# Detect and run appropriate test command
# pytest, jest, cargo test, go test, etc.
```

**If tests pass**: proceed to Phase 8.
**If tests fail**:

- Analyze failures
- Spawn `pipeline-coder` agent(s) to fix the failing code or tests (use judgment on which needs fixing)
- Re-run tests
- If tests still fail after 3 fix attempts, escalate to user

### 7.4 Re-run linters after fixes

If any code was changed during test fixes, re-run linters to ensure nothing regressed.

Update state file phase to `tests_passing`.

______________________________________________________________________

## Phase 8: Final Code Review

**Goal**: One last validation pass over ALL code (implementation + tests) together.

Spawn a `pipeline-code-reviewer` agent (model: **opus**) with:

```
Perform a FINAL review of ALL changes for this task:

## Task: <task description>

Read the plan at .mz/task/<task_name>/plan.md.
Read the file lists at .mz/task/<task_name>/implementation.md and .mz/task/<task_name>/tests.md.

Review ALL modified and created files (both implementation and tests).

This is the last gate before the task is declared complete. Check:
1. Implementation matches the plan completely
2. No dead code, unused imports, or debug artifacts
3. Code and tests are consistent with each other
4. No regressions to existing functionality
5. All reviewer feedback from previous rounds has been addressed

Output:
- **VERDICT**: PASS or FAIL
- **Issues** (if FAIL): numbered list with file:line references
```

**If FAIL**: Spawn `pipeline-coder` agent(s) to fix issues, then re-run linters and tests (Phase 7.2-7.4), then re-do this final review. Max 2 retries before escalating.

Update state file phase to `final_review_passed`.

______________________________________________________________________

## Phase 9: Optimization

**Goal**: Clean up the implementation — remove dead code, debug artifacts, unused imports, and unnecessary complexity.

### 9.1 Optimize

Spawn a `pipeline-optimizer` agent (model: **opus**) with:

```
Optimize the code that was implemented for this task.

## Scope
Read .mz/task/<task_name>/implementation.md and .mz/task/<task_name>/tests.md for the list of all files created or modified.

ONLY optimize these files. Do not touch other files.

Work through your full optimization checklist:
1. Debug artifacts (print statements, commented-out code, TODOs)
2. Dead code (unused functions, unreachable blocks)
3. Unused imports
4. Code duplication (within the modified files only)
5. Unnecessary complexity
6. Consistency

Report all changes made.
```

Save report to `.mz/task/<task_name>/optimization.md`.

### 9.2 Verify after optimization

Re-run linters and tests to ensure optimization didn't break anything.

**If any test regressed**: identify which optimization caused the regression from the report, revert that specific change, and re-run checks.

### 9.3 Review optimization

Spawn a `pipeline-code-reviewer` agent (model: **sonnet**) with:

```
Review the optimization changes made to this code.

The code was functionally complete and passing all tests and reviews before optimization.
Read .mz/task/<task_name>/optimization.md for what was changed.

Verify that:
1. No behavior was changed
2. Removals are genuinely dead (grep-verified, not just seemingly unused)
3. Simplifications are correct

Read all modified files and spot-check removals.

## VERDICT: PASS | FAIL
```

**If FAIL**: Spawn `pipeline-coder` to fix issues, re-run checks. Max 2 retries before escalating.

Update state file phase to `optimized`.

______________________________________________________________________

## Phase 10: Completeness Check

**Goal**: Verify the task is truly, fully complete.

Spawn a `pipeline-completeness-checker` agent (model: **opus**) with:

```
You are the final quality gate for a development task. Determine if the task is FULLY COMPLETE.

## Original Task
<task description>

## Context Files
Read the following files for context:
- .mz/task/<task_name>/plan.md (implementation plan)
- .mz/task/<task_name>/research.md (research findings)
- .mz/task/<task_name>/implementation.md (implementation file list)
- .mz/task/<task_name>/tests.md (test file list)

## Current State
- Linters: PASSING
- Tests: PASSING
- Code review: PASSED
- Test review: PASSED

Evaluate:
1. Does the implementation fulfill 100% of what was requested in the task description?
2. Are there any aspects of the task that were planned but not implemented?
3. Are there any aspects of the task that weren't even planned?
4. Would a user/stakeholder consider this task DONE?

Output:
- **VERDICT**: COMPLETE or INCOMPLETE
- If INCOMPLETE:
  - **Missing items**: what's not done
  - **Restart phase**: which phase to restart from (research/plan/code/test)
  - **Reason**: why that phase needs re-running
```

### 9.1 Handle verdict

**If COMPLETE**:

- Update state file status to `completed`
- Write a summary to `.mz/task/<task_name>/summary.md` listing all files changed, tests added, and key decisions
- Report to user: task is complete, here's what was done

**If INCOMPLETE**:

- Update state file with the restart phase and reason
- Jump to the indicated phase and re-execute from there
- Carry forward all existing artifacts — don't delete previous work
- Increment the top-level iteration counter in state.md
- If top-level iterations exceed 2, escalate to user instead of restarting

______________________________________________________________________

## Error Handling

- If any agent fails to spawn or returns an error, retry once. If it fails again, escalate to user.
- If the project has no test framework, tell the user and ask how to proceed.
- If the project has no linter, note it in the summary but don't block completion.
- Always save state before spawning agents so progress isn't lost on failure.

## State Management

After each phase completes, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Iteration counts for each review loop
- List of files modified
- Any escalation notes

This allows the pipeline to be resumed if interrupted.
