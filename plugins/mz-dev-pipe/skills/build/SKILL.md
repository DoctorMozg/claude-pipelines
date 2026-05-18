---
name: build
description: ALWAYS invoke when the user wants to build, implement, or create a new feature, module, or component from scratch. Triggers: "build X", "implement Y", "add feature". When NOT to use: bug fixes (use debug), polishing existing code (use polish).
argument-hint: <task description>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Development Pipeline (TDD)

## Overview

Orchestrates a full test-driven development lifecycle — research, plan, write failing tests (RED), implement to pass them (GREEN), review, refactor, and verify — using specialized sub-agents. Takes a task description and produces reviewed, tested, green code with explicit user approval at the plan gate.

The pipeline enforces red-green-refactor: tests are written and verified failing **before** any implementation code is allowed. Coders make tests pass without modifying them; refactor happens only after the green bar is restored.

## When to Use

- User asks to build, implement, or create a new feature/module/component.
- Triggers: "build X", "implement Y", "add feature Z", "develop".
- Work spans multiple files and benefits from a plan + review + test loop.

### When NOT to use

- Fixing a known bug — use `debug`.
- Making existing code meet quality criteria — use `polish`.
- Read-only analysis or impact mapping — use `audit` (or `audit depth:deep` for blast-radius-driven impact analysis).
- One-line edits or trivial tweaks — just edit directly.

## Input

- `$ARGUMENTS` — The task description. If empty, ask the user what they want built.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default**: `global`.
- Scope constrains **edits only**; researchers and verification commands may read the full project.

## Constants

- **MAX_REVIEW_ITERATIONS**: 3 | **MAX_RED_ITERATIONS**: 2 | **MAX_GREEN_ITERATIONS**: 3 | **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

| #   | Phase                                  | Reference                             | Loop?               |
| --- | -------------------------------------- | ------------------------------------- | ------------------- |
| 0   | Setup                                  | inline below                          | —                   |
| 1   | Research                               | `phases/research_and_planning.md`     | —                   |
| 2   | Planning + User Approval               | `phases/research_and_planning.md`     | plan review (max 3) |
| 3   | Test Writing (RED)                     | `phases/testing.md`                   | —                   |
| 4   | Test Review (3 parallel reviewers)     | `phases/testing.md`                   | max 3               |
| 5   | Verify RED                             | `phases/testing.md`                   | max 2               |
| 6   | Implementation (GREEN, parallel waves) | `phases/implementation_and_review.md` | —                   |
| 7   | Code Review                            | `phases/implementation_and_review.md` | max 3               |
| 8   | Lint, Format, and Verify GREEN         | `phases/implementation_and_review.md` | —                   |
| 9   | Final Code Review                      | `phases/finalization.md`              | max 2               |
| 10  | Refactor (Optimization)                | `phases/finalization.md`              | max 2               |
| 11  | Completeness Check                     | `phases/finalization.md`              | restart-from-phase  |

### Phase 0: Setup

Derive task name as `<YYYY_MM_DD>_build_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary (max 20 chars) of the description; on same-day collision append `_v2`, `_v3`.

**Resume check** (before creating the task directory): apply the entry contract in [`skills/shared/resume-protocol.md`](../shared/resume-protocol.md). Check for `.mz/task/<task_name>/state.md`:

- **No file** → fresh task. Proceed with directory creation and state write below.
- **Status: complete or aborted_by_user** → auto-suffix `_v2` / `_v3`, log the bump to chat, proceed as fresh task.
- **Status: running or failed** → present the Resume gate from `shared/resume-protocol.md`. On `Resume`, re-enter at the recorded `Phase` per the phase-idempotency rules. On `Restart`, archive the directory to `<task_name>_archived_<YYYY_MM_DD_HHMMSS>/` and start fresh. On `New`, suffix `_v2` and proceed fresh. Honor `MZ_DEV_PIPE_AUTO_APPROVE=1` per the protocol's auto-decision rules.

**Fresh-task setup**: create `.mz/task/<task_name>/`. Write `state.md` per the v2 schema in [`skills/shared/state-schema.md`](../shared/state-schema.md) — first line MUST be `schema_version: 2`, followed by `Status`, `Phase`, `PhaseName`, `Started`, `Iteration`, `FilesWritten`, and the progress-ledger keys `phase_complete: false` and `what_remains: []` (`last_verified` is omitted until the first gate passes). Use TaskCreate for per-phase tracking.

Then dispatch `pipeline-tooling-detector` to detect the project's test command, lint command, and formatter. Write to `.mz/task/<task_name>/tooling.md`. If `pipeline-tooling-detector` returns `BLOCKED` (no recognizable tooling), note it in `state.md` as `tooling: not_detected` and proceed — tooling failure is non-fatal at setup time.

### Phase 1: Research

Gather codebase context, assess feasibility, compare 2-3 approaches in parallel. See `phases/research_and_planning.md` → Phase 1. Update state to `research_complete`.

### Phase 2: Planning

Generate detailed plan, run plan-review loop, get user approval. See `phases/research_and_planning.md` → Phase 2.

#### 2.3 User approval gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

See [`skills/shared/approval-gate.md`](../shared/approval-gate.md) for the canonical two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format used below.

**Pre-read**: Read `.mz/task/<task_name>/plan.md` with the Read tool. Capture the full plan body (work units, test strategy, risks, verification criteria) into context. The plan must already have passed automated review before this gate fires.

**Compute the cost preview** before emitting the Surface 1 message:

- Count `N` from the plan: `N = 1 (test-writer) + 3 (test-reviewers) + W (parallel coder waves from plan.md work units) + 1 (code-reviewer) + 1 (final-reviewer) + 1 (optimizer) + 1 (completeness-checker)` where `W` is the number of work units in `plan.md`.
- Default per-agent budget: ~20k tokens (mixed Sonnet + Opus). For a typical 5-work-unit plan, `N ≈ 12`, total ≈ 240k tokens.
- Use the formula in `shared/approval-gate.md` to convert to a dollar estimate at the active price.

**Surface 1 — emit the plan message.** Output the plan verbatim as a normal markdown chat message. Emit the full verbatim contents of `.mz/task/<task_name>/plan.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Plan ready for review — build

<verbatim contents of plan.md>

---
**Approve** → proceed to Phase 3 (Test Writing — TDD/RED)  ·  **Reject** → task marked aborted, no files written  ·  reply with feedback to revise

Approve cost (estimated): <N> agents × ~20k tokens ≈ ~$<Y.YY> on mixed Sonnet+Opus
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the plan in the question body:

- question: `The plan above is ready for review. Approve to proceed, or Reject to abort — reply with feedback to revise.`
- options: **Approve** — proceed to Phase 3 (Test Writing — TDD/RED) · **Reject** — abort, no files written

**Response handling**:

- **Approve** → proceed to Phase 3.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → spawn `pipeline-planner` with feedback, overwrite `plan.md`. Do NOT re-run plan review — user's word is final. Return to Surface 1, re-read `.mz/task/<task_name>/plan.md`, and re-emit the entire plan message from scratch — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** → skip the AskUserQuestion call entirely, log `auto-approved (unattended mode)` to chat and to `state.md` under `## Auto-approvals`, and proceed to Phase 3. Surface 1 is still emitted so the transcript records what would have been approved. See `shared/approval-gate.md` for the bypass contract.

### Phase 3: Test Writing (RED)

Create tests **before any implementation** with `pipeline-test-writer` (model: opus). Tests assert the correct behavior the plan requires; since no production code exists yet, they will fail. See `phases/testing.md` → Phase 3.

### Phase 4: Test Review

Spawn TWO review agents in parallel (model: sonnet): the unified `pipeline-test-reviewer` (covers gaps + quality in one pass) and `pipeline-code-reviewer` (test-code craftsmanship). The reviewers verify the tests cover every work unit from the plan and that they would catch real regressions. See `phases/testing.md` → Phase 4. Update state to `test_review_passed`.

### Phase 5: Verify RED

Run the new tests and confirm they FAIL (or error with `not implemented` / missing-symbol errors). A test that passes against zero implementation is broken — it would not catch a regression. Re-dispatch `pipeline-test-writer` with the unexpectedly-passing test names if any pass. See `phases/testing.md` → Phase 5. Update state to `red_verified`.

### Phase 6: Implementation (GREEN)

Parse work units into execution waves and dispatch parallel `pipeline-coder` agents (model: opus). Each coder is told the relevant failing tests and instructed to make them pass **without modifying any test file**. After each wave, update state with `current_wave: N`, per-coder STATUS, and cumulative files modified — required for safe resumption if context compacts. See `phases/implementation_and_review.md` → Phase 6. Update state to `implementation_complete`.

### Phase 7: Code Review

Review with `pipeline-code-reviewer` (model: opus), iterate fixes up to 3 times. See `phases/implementation_and_review.md` → Phase 7. Update state to `code_review_passed`.

### Phase 8: Lint, Format, and Verify GREEN

Detect tooling, run linters/formatters, then run the **full test suite** including the Phase 3 tests. All target tests must now pass; no pre-existing tests may regress. See `phases/implementation_and_review.md` → Phase 8. Update state to `tests_passing`.

### Phase 9: Final Code Review

Last validation pass over ALL code with `pipeline-code-reviewer`. See `phases/finalization.md` → Phase 9. Update state to `final_review_passed`.

### Phase 10: Refactor (Optimization)

Clean up dead code, debug artifacts, unused imports — the refactor leg of red-green-refactor. Tests must remain green; no behavior change. Re-verify then review. See `phases/finalization.md` → Phase 10. Update state to `optimized`.

### Phase 11: Completeness Check

Final gate: `pipeline-completeness-checker` (model: opus) decides if the task is done. See `phases/finalization.md` → Phase 11. Max 2 iterations.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                 | Rebuttal                                                                                                    |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| "plan is fine without review"                   | "plan review catches integration gaps that become 3 review cycles downstream"                               |
| "tests can wait until after first ship"         | "missing tests on Day 1 become 'why is this flaky?' in Week 2"                                              |
| "one big commit is easier"                      | "atomic commits are the only way to bisect a regression cheaply"                                            |
| "I'll write code first, tests are easier after" | "tests written after the code mirror the implementation; tests written first describe the behavior"         |
| "skip the RED check, of course they fail"       | "tests that pass against missing code are silently broken — Phase 5 catches mock-only or import-only tests" |

## Red Flags

- You dispatched coders without user approval of the plan.
- Plan review was skipped or truncated to save time.
- A coder agent was dispatched before tests were written and verified RED.
- A coder modified or deleted a test to make it pass.
- Phase 5 was skipped on the assumption that tests "must" fail without implementation.

## Verification

Output the final state block: task dir path, all phases marked complete, review iteration counts, file list, and tests-passing status. If any phase is incomplete, print the blocker explicitly.

## Error Handling

Agent failure → retry once, then escalate. No test framework → ask how to proceed. No linter → note in summary, don't block. Always save state before spawning agents.

## State Management

After each phase, update `state.md` with current phase, iteration counts, files modified, and escalation notes. Allows resumption if interrupted.

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a lint/test/review gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade.
