---
name: audit
description: ALWAYS invoke when the user wants to audit, find bugs, or review the codebase for issues. Triggers: "audit", "find bugs", "security review", "check for issues", "code quality scan". Multi-lens bug and improvement hunter — researches across correctness, security, performance, maintainability, and reliability lenses, ranks findings, gets approval, then dispatches parallel fixes with review. Optional argument to focus scope or lenses.
argument-hint: [scope:branch|global|working] [optional focus — e.g. "concurrency bugs", "audit src/auth", "security review"]
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Problem-Locator Pipeline

You orchestrate a multi-agent codebase audit. Run parallel researchers across lenses (correctness, security, performance, maintainability, reliability), consolidate and rank findings, get user approval, dispatch parallel coders to fix and mirrored reviewers to validate. Critical/high fixes get regression tests.

## Input

- `$ARGUMENTS` — Optional: lens hint (`"security review"`), scope hint (`"src/auth/"`), combined (`"security audit of src/auth/"`), or empty (roam mode — full repo minus vendored/generated/test files). If ambiguous, ask via AskUserQuestion. Never guess.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present. Remove before parsing lens/scope hints. `scope:` controls files, remaining text controls lenses (orthogonal).

- **`branch`** — `git diff $(git merge-base HEAD <base>)..HEAD --name-only` (try `main`, then `master`). Warn if on base branch.
- **`global`** — All source files, honoring `.gitignore`. Exclude vendored, generated, lock, test files, >5000 LOC.
- **`working`** — `git diff HEAD --name-only` + `git ls-files --others --exclude-standard`. Warn if empty.
- **Default** — path-like tokens → expand scope, no path tokens → roam.

## Core Principles

1. **Research first, fix later.** Do not touch code until findings are approved.
1. **Parallel where safe, sequential where necessary.** Ask when unclear.

## Constants

- **MAX_RESEARCHERS**: 5 | **MAX_CODERS**: 6 | **MAX_REVIEWERS**: 6
- **MAX_REVIEW_ITERATIONS**: 3 | **MAX_FIX_ATTEMPTS**: 3
- **CRITICAL_CAP**: unlimited | **HIGH_CAP**: 10 | **MEDIUM_CAP**: 5 | **LOW_CAP**: 0 (count only)
- **REGRESSION_TEST_SEVERITIES**: `[critical, high]` | **TASK_DIR**: `.mz/task/`

## Phase Overview

| #   | Phase                  | Reference                       | Loop?                   |
| --- | ---------------------- | ------------------------------- | ----------------------- |
| 0   | Setup                  | inline below                    | —                       |
| 1   | Scope & Lens Selection | `phases/research.md`            | —                       |
| 2   | Multi-Lens Research    | `phases/research.md`            | —                       |
| 3   | Consolidate & Rank     | `phases/research.md`            | —                       |
| 3.5 | User Approval Gate     | inline below                    | re-research on feedback |
| 4   | Chunk Findings         | `phases/fix_and_verify.md`      | —                       |
| 5   | Parallel Fix           | `phases/fix_and_verify.md`      | —                       |
| 6   | Verify & Auto-Fix      | `phases/fix_and_verify.md`      | inner fix loop (max 3)  |
| 7   | Parallel Review        | `phases/review_and_finalize.md` | —                       |
| 8   | Handle Verdicts        | `phases/review_and_finalize.md` | respawn loop (max 3)    |
| 9   | Regression Tests       | `phases/review_and_finalize.md` | —                       |
| 10  | Final Summary          | `phases/review_and_finalize.md` | —                       |

## Phase 0: Setup

Derive task name as `audit_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) of the argument (or "roam") and HHMMSS is current time. Create `.mz/task/<task_name>/`. Write `state.md` with Status, Phase, Started, Review iterations, Fix attempts, Lenses dispatched, Findings. Use TaskCreate for per-phase tracking.

## Phase 1: Scope & Lens Selection

Parse argument into (scope, lens). Pure path → all 5 lenses narrowed. Lens keywords → matching lenses on roam. Ambiguous → ask.

**See `phases/research.md` → Phase 1** for keyword-matching and path detection. Update state to `scope_selected`.

## Phase 2: Multi-Lens Research

Dispatch 1-5 `pipeline-researcher` agents (model: sonnet) in a single message, one per lens.

**See `phases/research.md` → Phase 2** for lens-specific prompts and artifact format. Update state to `researched`.

## Phase 3: Consolidate & Rank

Merge lens outputs, dedupe, rank by severity then confidence, apply caps. Zero findings >= medium → report clean, exit.

**See `phases/research.md` → Phase 3** for dedup, ranking, and `findings.md` artifact. Update state to `findings_ranked`.

## Phase 3.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: summary counts by severity, scope used, ranked findings (file:line, severity, confidence, description, proposed fix), coder assignment preview.

Use AskUserQuestion with:

```
Found <N> actionable findings. Please review:

<findings list>

Reply 'approve' to proceed with fixes, 'reject' to abort, or provide feedback for changes
(e.g. "drop finding 3", "rerun research with security lens only", "narrow scope to src/api/").
```

**Response handling**:

- **"approve"** → proceed to Phase 4.
- **"reject"** → abort.
- **Feedback** — *drop/adjust* → remove and re-present (no re-research). *Scope/lens changes* → Phase 1, then re-present. *Unclear* → ask follow-up. Loop until explicit approval.

## Phase 4: Chunk Findings

Group by affected file. Same file → same coder. Wave size \<= `MAX_CODERS`.

**See `phases/fix_and_verify.md` → Phase 4** for chunking algorithm. Update state to `chunked`.

## Phase 5: Parallel Fix

Dispatch up to 6 `pipeline-coder` agents (model: opus) per wave, one per chunk.

**See `phases/fix_and_verify.md` → Phase 5** for coder dispatch and "trivially adjacent" rule.

## Phase 6: Verify & Auto-Fix

Re-run tests/linters. Must restore green before Phase 7.

**See `phases/fix_and_verify.md` → Phase 6** for inner fix loop (max 3) and escalation. Update state to `verified_green`.

## Phase 7: Parallel Review

Dispatch `pipeline-code-reviewer` agents (model: opus), one per chunk (1:1 mirror).

**See `phases/review_and_finalize.md` → Phase 7** for dispatch prompt and `review_<iteration>.md` artifact.

## Phase 8: Handle Verdicts

Re-dispatch rejected chunks only. Approved chunks frozen.

**See `phases/review_and_finalize.md` → Phase 8** for decision tree and respawn loop (max 3). Update state to `review_passed` when all PASS.

## Phase 9: Regression Tests

For critical/high findings, dispatch `pipeline-test-writer` agents (model: opus).

**See `phases/review_and_finalize.md` → Phase 9** for test writer dispatch and verification.

## Phase 10: Final Summary

Write `summary.md` listing findings, fixes, tests, iterations, follow-ups.

**See `phases/review_and_finalize.md` → Phase 10** for summary template. Update state to `completed`.

## Error Handling

- **Ambiguous argument**: ask before Phase 1. **Empty scope / zero findings**: report and exit.
- **No test framework**: ask user for command. **No linter**: note and skip.
- **Researcher fails**: continue with remaining lenses, flag in Phase 3.5.
- **Write conflict**: sequentialize next iteration. **Regression test fails**: escalate to user.

## State Management

Update `state.md` after each phase with current phase, iteration counts, files modified, escalation notes. Allows resumption if interrupted.
