---
name: polish
description: ALWAYS invoke when the user wants to polish code against criteria — fix failing tests, meet quality standards. Triggers: "polish X", "make tests pass", "fix failing tests". When NOT to use: new feature (use build), single bug (use debug).
argument-hint: [scope:branch|global|working] <completion criteria — what must pass, what must be fixed, what must work>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Polishing Pipeline

## Overview

Orchestrates iterative polish of existing code against specific completion criteria. Unlike `build` which builds from scratch, polish works with what's already there — running tests, diagnosing failures, fixing issues with review loops, and optimizing.

When a behavioral criterion is not yet covered by any test, polish writes the test first (TDD-style), verifies it fails against the current code, then fixes. This keeps every fix anchored to a regression-catching assertion.

## When to Use

- User has existing code that needs to meet specific criteria or quality standards.
- Triggers: "polish X", "make tests pass", "fix failing tests", "clean up the code", "finish this implementation".
- Code exists but is failing tests, lint, or quality gates.

### When NOT to use

- Starting a new feature from scratch — use `build`.
- A single isolated bug with a reproducer — use `debug`.
- If the root cause of failures is known (e.g., a specific bug was identified) — use `debug` to fix the root cause first, then return to `polish` for quality criteria.
- Read-only verification with no fix intent — use `verify`.
- Map-reduce dead-code cleanup — use `cleanup`.

## Input

- `$ARGUMENTS` — The completion criteria. This can be:
  - "All tests in test_foo.py must pass"
  - "Pre-commit hooks must pass on all changed files"
  - "The WebSocket reconnection must handle timeout correctly"
  - "Fix all failing tests and clean up the implementation"
  - Any combination of pass/fail criteria and behavioral requirements

If empty, ask the user what needs to be polished.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default** (no `scope:`): all project files eligible for edits.
- `scope:` controls **which files agents may edit**. Tests and linters always run on the full project. Criteria determine **what to verify**; scope determines **where fixes may be applied**.

## Constants

- **MAX_FIX_ITERATIONS**: 5 — max code-test-review cycles before escalating
- **MAX_REVIEW_RETRIES**: 3 — max times a review can fail before escalating
- **TASK_DIR**: `.mz/task/` in the project root

## Core Process

### Phase Overview

| Phase | Goal                 | Details                             |
| ----- | -------------------- | ----------------------------------- |
| 0     | Setup                | Inline below                        |
| 1     | Initial Assessment   | `phases/assess_and_fix.md`          |
| 1.5   | User Approval Gate   | Inline below                        |
| 2     | Quick Fixes          | `phases/assess_and_fix.md`          |
| 3     | Research (if needed) | `phases/assess_and_fix.md`          |
| 4     | Fix-Test-Review Loop | `phases/fix_review_and_finalize.md` |
| 5     | Optimization         | `phases/fix_review_and_finalize.md` |
| 6     | Final Verification   | `phases/fix_review_and_finalize.md` |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

### Phase 0: Setup

1. **Resolve scope** — if `scope:` extracted, resolve to a concrete file list and save to `.mz/task/<task_name>/scope_files.txt`. Otherwise all project files eligible.
1. **Parse criteria** — break input into a checklist of discrete, verifiable criteria (e.g. "all tests pass", "pre-commit clean", "no debug prints in src/").
1. **Task name** — `<YYYY_MM_DD>_polish_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is snake_case of criteria (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. **Task dir & state** — apply the resume-check contract in [`skills/shared/resume-protocol.md`](../shared/resume-protocol.md): if `.mz/task/<task_name>/state.md` exists with `Status: running | failed`, present the Resume gate before proceeding. Otherwise create `.mz/task/<task_name>/` and write `state.md` per [`skills/shared/state-schema.md`](../shared/state-schema.md) — first line MUST be `schema_version: 2`, followed by required keys (`Status`, `Phase`, `Started`, `Iteration` (0), `FilesWritten`, `phase_complete: false`, `what_remains: []`) plus the parsed criteria checklist as a skill-specific key.
1. **Task tracking** — TaskCreate per pipeline phase. Then read `phases/assess_and_fix.md` and proceed to Phase 1.

### Phase 1.5: User Approval Gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

See [`skills/shared/approval-gate.md`](../shared/approval-gate.md) for the canonical two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format used below.

**Pre-read**: Read `.mz/task/<task_name>/assessment.md` with the Read tool and capture its full contents into context.

**Surface 1 — emit the plan message.** Output the assessment verbatim as a normal markdown chat message. Emit the full verbatim contents of `.mz/task/<task_name>/assessment.md` — do not substitute a path, status summary, line count, or `<failing criteria list>` / `<proposed quick-fix plan>` / `<estimated file count>` placeholders. Structure:

```
## Assessment ready for review — polish

<verbatim contents of assessment.md>

---
**Approve** → proceed to Phase 2 (Quick Fixes)  ·  **Reject** → mark task aborted, stop here  ·  reply with feedback to revise

Approve cost (estimated): <N> agents × ~20k tokens ≈ ~$<Y.YY> on mixed Sonnet+Opus
```

Compute `<N>` from `assessment.md` quick-fix count plus the maximum review-loop budget (`MAX_FIX_ITERATIONS × (1 fix + 1 test + 1 review)`). Use the `shared/approval-gate.md` formula to convert to a dollar estimate.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the assessment in the question body, it lives in the plan message above:

- question: `The assessment above is ready for review.`
- options: **Approve** — proceed to Phase 2 (Quick Fixes) · **Reject** — mark task aborted, stop here

**Response handling**:

- **Approve** → update state, proceed to Phase 2.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → incorporate, re-run Phase 1 if needed, overwrite `assessment.md`, return to this gate, re-read `assessment.md`, and re-emit the entire plan message from scratch with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. Then re-present the selector. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** → skip the AskUserQuestion call entirely, log `auto-approved (unattended mode)` to chat and to `state.md` under `## Auto-approvals`, and proceed to Phase 2. The plan message (Surface 1) is still emitted so the transcript records what would have been approved. See `shared/approval-gate.md` for the bypass contract.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                      | Rebuttal                                                 |
| ------------------------------------ | -------------------------------------------------------- |
| "good enough, ship"                  | "polish is the last line of defense before users see it" |
| "edge cases are rare"                | "every bug report you've ever gotten is an edge case"    |
| "tests are green, refactor can wait" | "green-test refactor debt compounds"                     |

## Red Flags

- Edge cases were deferred to "next sprint" instead of handled now.
- Code was declared "good enough" without a final criteria sweep.
- Polish was equated with refactor — criteria drifted mid-loop.

## Verification

Output the final criteria checklist with every item checked, along with the test run status, lint status, and iteration count. Any unchecked item blocks completion.

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

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a verification gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade.
