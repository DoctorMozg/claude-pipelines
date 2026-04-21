---
name: build
description: ALWAYS invoke when the user wants to build, implement, or create a new feature, module, or component from scratch. Triggers: "build X", "implement Y", "add feature". When NOT to use: bug fixes (use debug), polishing existing code (use polish).
argument-hint: <task description>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Development Pipeline

## Overview

Orchestrates a full development lifecycle — research, plan, implement in parallel waves, review, test, optimize, and verify — using specialized sub-agents. Takes a task description and produces reviewed, tested, green code with explicit user approval at the plan gate.

## When to Use

- User asks to build, implement, or create a new feature/module/component.
- Triggers: "build X", "implement Y", "add feature Z", "develop".
- Work spans multiple files and benefits from a plan + review + test loop.

### When NOT to use

- Fixing a known bug — use `debug`.
- Making existing code meet quality criteria — use `polish`.
- Read-only analysis or impact mapping — use `blast-radius` or `audit`.
- One-line edits or trivial tweaks — just edit directly.

## Input

- `$ARGUMENTS` — The task description. If empty, ask the user what they want built.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default**: `global`.
- Scope constrains **edits only**; researchers and verification commands may read the full project.

## Constants

- **MAX_REVIEW_ITERATIONS**: 3 | **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

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

### Phase 0: Setup

Derive task name as `<YYYY_MM_DD>_build_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary (max 20 chars) of the description; on same-day collision append `_v2`, `_v3`. Create `.mz/task/<task_name>/`. Write `state.md` with Status, Phase, Started, Iterations. Use TaskCreate for per-phase tracking.

Then dispatch `pipeline-tooling-detector` to detect the project's test command, lint command, and formatter. Write to `.mz/task/<task_name>/tooling.md`. If `pipeline-tooling-detector` returns `BLOCKED` (no recognizable tooling), note it in `state.md` as `tooling: not_detected` and proceed — tooling failure is non-fatal at setup time.

### Phase 1: Research

Gather codebase context, assess feasibility, compare 2-3 approaches in parallel. See `phases/research_and_planning.md` → Phase 1. Update state to `research_complete`.

### Phase 2: Planning

Generate detailed plan, run plan-review loop, get user approval. See `phases/research_and_planning.md` → Phase 2.

#### 2.3 User approval gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Plan ready for review**
The implementation plan passed automated review and is ready for your approval. It covers all phases, files affected, and estimated scope.

- **Approve** → proceed to Phase 3 implementation
- **Reject** → task marked aborted, no files written
- **Feedback** → re-run planning with your input, loop back here
```

Use AskUserQuestion with:

```
The implementation plan is ready and passed review. Please review and approve:

<contents of plan.md>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → proceed to Phase 3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → spawn `pipeline-planner` with feedback, overwrite `plan.md`, re-present via AskUserQuestion. Do NOT re-run plan review — user's word is final. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.

### Phase 3: Implementation

Parse work units into execution waves and dispatch parallel `pipeline-coder` agents (model: opus). See `phases/implementation_and_review.md` → Phase 3. Update state to `implementation_complete`.

**After each wave completes (all coders in the wave return), update `.mz/task/<task_name>/state.md` with:**

- `current_wave: N`
- Per-coder results: STATUS (`DONE` / `DONE_WITH_CONCERNS` / `BLOCKED` / `NEEDS_CONTEXT`) for each work unit
- Cumulative list of files modified (from `implementation.md` or each coder's artifact)

This state update is mandatory — it enables safe resumption if context is compacted between waves.

### Phase 4: Code Review

Review with `pipeline-code-reviewer` (model: opus), iterate fixes up to 3 times. See `phases/implementation_and_review.md` → Phase 4. Update state to `code_review_passed`.

### Phase 5: Test Writing

Create tests with `pipeline-test-writer` (model: opus). See `phases/testing.md` → Phase 5.

### Phase 6: Test Review

Spawn THREE review agents in parallel (model: sonnet): coverage, quality, code. See `phases/testing.md` → Phase 6. Update state to `test_review_passed`.

### Phase 7: Lint, Format, and Test Run

Detect tooling, run linters/formatters, then run tests. See `phases/testing.md` → Phase 7. Update state to `tests_passing`.

### Phase 8: Final Code Review

Last validation pass over ALL code with `pipeline-code-reviewer`. See `phases/finalization.md` → Phase 8. Update state to `final_review_passed`.

### Phase 9: Optimization

Clean up dead code, debug artifacts, unused imports. Re-verify then review. See `phases/finalization.md` → Phase 9. Update state to `optimized`.

### Phase 10: Completeness Check

Final gate: `pipeline-completeness-checker` (model: opus) decides if the task is done. See `phases/finalization.md` → Phase 10. Max 2 iterations.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                         | Rebuttal                                                                      |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| "plan is fine without review"           | "plan review catches integration gaps that become 3 review cycles downstream" |
| "tests can wait until after first ship" | "missing tests on Day 1 become 'why is this flaky?' in Week 2"                |
| "one big commit is easier"              | "atomic commits are the only way to bisect a regression cheaply"              |

## Red Flags

- You dispatched coders without user approval of the plan.
- Plan review was skipped or truncated to save time.
- Tests were deferred to "later" instead of written in Phase 5.

## Verification

Output the final state block: task dir path, all phases marked complete, review iteration counts, file list, and tests-passing status. If any phase is incomplete, print the blocker explicitly.

## Error Handling

Agent failure → retry once, then escalate. No test framework → ask how to proceed. No linter → note in summary, don't block. Always save state before spawning agents.

## State Management

After each phase, update `state.md` with current phase, iteration counts, files modified, and escalation notes. Allows resumption if interrupted.
