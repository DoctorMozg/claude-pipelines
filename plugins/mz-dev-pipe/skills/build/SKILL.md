---
name: build
description: ALWAYS invoke when the user wants to build, implement, or create a new feature, module, or component from scratch. Triggers: "build X", "implement Y", "create Z", "add feature", "develop". Full autonomous development pipeline — researches feasibility, plans with approach comparison, codes in parallel waves, reviews, tests, optimizes, and verifies completeness. Provide a task description as the argument.
argument-hint: <task description>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Development Pipeline

You are an orchestrator that drives a full development lifecycle using specialized sub-agents.
You receive a task description and autonomously research, plan, implement, review, and test it.

## Input

- `$ARGUMENTS` — The task description. If empty, ask the user what they want built.

## Constants

- **MAX_REVIEW_ITERATIONS**: 3 | **TASK_DIR**: `.mz/task/`

## Phase Overview

| #   | Phase                              | Reference                             | Loop?               |
| --- | ---------------------------------- | ------------------------------------- | ------------------- |
| 0   | Setup                              | inline below                          | —                   |
| 1   | Research                           | `phases/research_and_planning.md`     | —                   |
| 2   | Planning + User Approval           | `phases/research_and_planning.md`     | plan review (max 3) |
| 3   | Implementation (parallel waves)    | `phases/implementation_and_review.md` | —                   |
| 4   | Code Review                        | `phases/implementation_and_review.md` | max 3               |
| 5   | Test Writing                       | `phases/testing.md`                   | —                   |
| 6   | Test Review (3 parallel reviewers) | `phases/testing.md`                   | max 3               |
| 7   | Lint, Format, and Test Run         | `phases/testing.md`                   | —                   |
| 8   | Final Code Review                  | `phases/finalization.md`              | max 2               |
| 9   | Optimization                       | `phases/finalization.md`              | max 2               |
| 10  | Completeness Check                 | `phases/finalization.md`              | restart-from-phase  |

## Phase 0: Setup

Derive a short snake_case task name (max 30 chars) from the description. Create `.mz/task/<task_name>/`. Write `state.md` with Status, Phase, Started, Iterations. Use TaskCreate for per-phase tracking.

## Phase 1: Research

Gather codebase context, assess feasibility, compare 2-3 approaches in parallel.

**See `phases/research_and_planning.md` → Phase 1** for researcher dispatch and `research.md` artifact.

Update state phase to `research_complete`.

## Phase 2: Planning

Generate a detailed plan, run the plan-review loop, then get user approval.

**See `phases/research_and_planning.md` → Phase 2** for planner/reviewer dispatch and `plan.md` artifact.

### 2.3 User approval gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Use AskUserQuestion with:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → proceed to Phase 3.
- **"reject"** → abort.
- **Feedback** → spawn `pipeline-planner` with feedback, overwrite `plan.md`, re-present via AskUserQuestion. Do NOT re-run plan review — user's word is final. Loop until explicit approval.

## Phase 3: Implementation

Parse work units into execution waves and dispatch parallel `pipeline-coder` agents (model: opus).

**See `phases/implementation_and_review.md` → Phase 3** for wave scheduling and coder dispatch.

Update state phase to `implementation_complete`.

## Phase 4: Code Review

Review with `pipeline-code-reviewer` (model: opus), iterate fixes up to 3 times.

**See `phases/implementation_and_review.md` → Phase 4** for review prompt and verdict handling.

Update state phase to `code_review_passed`.

## Phase 5: Test Writing

Create tests with `pipeline-test-writer` (model: opus).

**See `phases/testing.md` → Phase 5** for test-writer dispatch and `tests.md` artifact.

## Phase 6: Test Review

Spawn THREE review agents in parallel (model: sonnet): coverage, quality, code.

**See `phases/testing.md` → Phase 6** for dispatch, consolidation, and review loop (max 3).

Update state phase to `test_review_passed`.

## Phase 7: Lint, Format, and Test Run

Detect project tooling, run linters/formatters, then run tests.

**See `phases/testing.md` → Phase 7** for tooling detection and test-fix loop (max 3).

Update state phase to `tests_passing`.

## Phase 8: Final Code Review

Last validation pass over ALL code with `pipeline-code-reviewer` (model: opus).

**See `phases/finalization.md` → Phase 8** for final review and fix-and-retry (max 2).

Update state phase to `final_review_passed`.

## Phase 9: Optimization

Clean up dead code, debug artifacts, unused imports. Re-verify, then review.

**See `phases/finalization.md` → Phase 9** for sub-phases and regression-revert logic.

Update state phase to `optimized`.

## Phase 10: Completeness Check

Final gate: `pipeline-completeness-checker` (model: opus) decides if the task is done.

**See `phases/finalization.md` → Phase 10** for completeness prompt and restart-from-phase logic. Max 2 iterations before escalating.

## Error Handling

- Agent failure → retry once, then escalate to user.
- No test framework → tell user and ask how to proceed.
- No linter → note in summary, don't block.
- Always save state before spawning agents.

## State Management

After each phase, update `state.md` with current phase, iteration counts, files modified, and escalation notes. Allows resumption if interrupted.
