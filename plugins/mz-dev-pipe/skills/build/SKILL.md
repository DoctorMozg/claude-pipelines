---
name: build
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

The pipeline runs eleven phases (0-10). Phase 0 is inline setup. Phases 1-10 have their full dispatch detail in the matching reference file under `phases/`. Follow the pointers below when entering each phase.

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

Gather codebase context, assess feasibility, compare 2-3 implementation approaches, and optionally research external domain knowledge — all in parallel.

**See `phases/research_and_planning.md` → Phase 1** for full dispatch detail on `pipeline-researcher` agents (codebase exploration, feasibility & approach analysis, optional domain research) and the `.mz/task/<task_name>/research.md` artifact.

After completion, update state file phase to `research_complete`.

______________________________________________________________________

## Phase 2: Planning

Generate a detailed plan, run the plan-review loop, then get user approval.

**See `phases/research_and_planning.md` → Phase 2** for full dispatch detail on `pipeline-planner` (model: opus) and `pipeline-plan-reviewer` (model: sonnet), including the review loop with `MAX_REVIEW_ITERATIONS = 3`, escalation logic, and the final `.mz/task/<task_name>/plan.md` artifact.

### 2.3 User approval gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Use AskUserQuestion with:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update state to `plan_approved`, proceed to Phase 3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → spawn `pipeline-planner` again with the feedback, overwrite `plan.md`, then return to this gate and re-present **via AskUserQuestion** using the same format. Do NOT re-run the plan review loop — the user's word is final. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.

______________________________________________________________________

## Phase 3: Implementation

Parse work units from the approved plan into execution waves and dispatch parallel `pipeline-coder` agents (model: opus) per work unit.

**See `phases/implementation_and_review.md` → Phase 3** for full wave scheduling rules, coder dispatch prompt, and the `.mz/task/<task_name>/implementation.md` artifact.

Update state file phase to `implementation_complete`.

______________________________________________________________________

## Phase 4: Code Review

Review the implementation with `pipeline-code-reviewer` (model: opus) and iterate fixes up to 3 times.

**See `phases/implementation_and_review.md` → Phase 4** for the review prompt, verdict handling, and parallel fix dispatch.

Update state file phase to `code_review_passed`.

______________________________________________________________________

## Phase 5: Test Writing

Create tests for the implementation with `pipeline-test-writer` (model: opus).

**See `phases/testing.md` → Phase 5** for the test-writer dispatch prompt and the `.mz/task/<task_name>/tests.md` artifact.

______________________________________________________________________

## Phase 6: Test Review

Spawn THREE review agents **in parallel** (all model: sonnet): coverage, quality, and code.

**See `phases/testing.md` → Phase 6** for the three dispatch prompts, consolidation logic, and the review loop (max 3 iterations).

Update state file phase to `test_review_passed`.

______________________________________________________________________

## Phase 7: Lint, Format, and Test Run

Detect project tooling, run linters and formatters, then run tests.

**See `phases/testing.md` → Phase 7** for tooling detection, common command patterns, and the test-fix loop (max 3 attempts before escalation).

Update state file phase to `tests_passing`.

______________________________________________________________________

## Phase 8: Final Code Review

One last validation pass over ALL code (implementation + tests) with `pipeline-code-reviewer` (model: opus).

**See `phases/finalization.md` → Phase 8** for the final review prompt and the fix-and-retry flow (max 2 retries).

Update state file phase to `final_review_passed`.

______________________________________________________________________

## Phase 9: Optimization

Clean up dead code, debug artifacts, and unused imports with `pipeline-optimizer` (model: opus). Re-verify, then review the optimization with `pipeline-code-reviewer` (model: sonnet).

**See `phases/finalization.md` → Phase 9** for the three sub-phases (optimize, verify, review optimization) and the regression-revert logic.

Update state file phase to `optimized`.

______________________________________________________________________

## Phase 10: Completeness Check

Final gate: `pipeline-completeness-checker` (model: opus) decides whether the task is truly done.

**See `phases/finalization.md` → Phase 10** for the completeness prompt and the restart-from-phase logic. If INCOMPLETE, jump to the indicated phase and carry forward all existing artifacts. Max 2 top-level iterations before escalating to user.

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
