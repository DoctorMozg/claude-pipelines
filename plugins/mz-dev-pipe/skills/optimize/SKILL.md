---
name: optimize
description: ALWAYS invoke when the user wants to optimize, clean up, or reduce complexity in existing code. Triggers: "optimize X", "clean up", "refactor", "reduce complexity", "remove dead code". Map-reduce optimization pipeline — scans scope, builds import graph, dispatches parallel optimizers with mirrored reviewers, iterates on rejections. Provide scope as the argument.
argument-hint: [scope:branch|global|working] <scope: glob, directory, git range, or free-text description>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Code Optimization Pipeline

You orchestrate a multi-agent optimization pass over existing code. Build import-graph-based chunking, dispatch parallel `pipeline-optimizer` agents with mirrored `pipeline-code-reviewer` agents per chunk. On rejection, respawn rejected chunks only. Tests and linters run after each batch; auto-fix regressions before review.

## Input

- `$ARGUMENTS` — The scope: glob (`"src/**/*.py"`), directory (`"src/auth/"`), git range (`"origin/main..HEAD"`), or free-text (`"the authentication module"`). Auto-detect form. If ambiguous or empty, ask — do not guess.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present. Remove before applying detection logic.

- **`branch`** — `git diff $(git merge-base HEAD <base>)..HEAD --name-only` (try `main`, then `master`). Warn if on base branch.
- **`global`** — All source files, honoring `.gitignore`. Exclude vendored, generated, lock files, >5000 LOC.
- **`working`** — `git diff HEAD --name-only` + `git ls-files --others --exclude-standard`. Warn if empty.
- **Default** — use existing detection (glob / directory / git range / free-text). If `scope:` given alongside explicit argument, they intersect.

## Core Principles

1. **Behavior preservation is non-negotiable.** Tests and linters run between every batch.
1. **Parallel where safe, sequential where necessary.** Ask when unclear.

## Constants

- **MAX_OPTIMIZERS**: 6 | **MAX_REVIEWERS**: 6
- **MAX_REVIEW_ITERATIONS**: 3 | **MAX_FIX_ATTEMPTS**: 3 | **TASK_DIR**: `.mz/task/`

## Phase Overview

| #   | Phase                 | Reference                       | Loop?                  |
| --- | --------------------- | ------------------------------- | ---------------------- |
| 0   | Setup                 | inline below                    | —                      |
| 1   | Scan & Chunk          | `phases/scan_and_plan.md`       | —                      |
| 2   | Baseline Snapshot     | `phases/scan_and_plan.md`       | —                      |
| 2.5 | User Approval Gate    | inline below                    | re-plan on feedback    |
| 3   | Parallel Optimization | `phases/optimize_and_verify.md` | —                      |
| 4   | Verify & Auto-Fix     | `phases/optimize_and_verify.md` | inner fix loop (max 3) |
| 5   | Parallel Review       | `phases/review_and_finalize.md` | —                      |
| 6   | Handle Verdicts       | `phases/review_and_finalize.md` | respawn loop (max 3)   |
| 7   | Final Summary         | `phases/review_and_finalize.md` | —                      |

## Phase 0: Setup

Derive task name as `optimize_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) of the scope and HHMMSS is current time. Create `.mz/task/<task_name>/`. Write `state.md` with Status, Phase, Started, Review iterations, Fix attempts, Files in scope, Chunks. Use TaskCreate for per-phase tracking.

## Phase 1: Scan & Chunk

Resolve input to file list, build import graph, group into 1-6 chunks using SCCs and module boundaries.

**See `phases/scan_and_plan.md` → Phase 1** for scope resolution, graph construction, and chunking.

Update state phase to `scanned`.

## Phase 2: Baseline Snapshot

Run tests and linters once to capture pre-optimization state. Required before optimizers touch code.

**See `phases/scan_and_plan.md` → Phase 2** for tooling detection and `baseline.md` artifact.

Update state phase to `baseline_captured`.

## Phase 2.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: resolved scope, chunk breakdown with rationale, optimizer/reviewer counts, baseline status, flagged risks. **If baseline was RED**: include prominently, ask whether to proceed/abort/run `polish` first.

Use AskUserQuestion with:

```
The optimization plan is ready. Please review and approve:

<plan contents>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes
(e.g. exclude a file, adjust chunking, change chunk count).
```

**Response handling**:

- **"approve"** → proceed to Phase 3.
- **"reject"** → abort.
- **Feedback** → apply changes, overwrite `scan.md`, re-present via AskUserQuestion. Loop until explicit approval.

## Phase 3: Parallel Optimization

Dispatch N `pipeline-optimizer` agents (model: opus) in a single message, one per chunk.

**See `phases/optimize_and_verify.md` → Phase 3** for dispatch prompts and conflict detection.

## Phase 4: Verify & Auto-Fix

Re-run tests/linters. Must restore green before Phase 5.

**See `phases/optimize_and_verify.md` → Phase 4** for inner fix loop (max 3) and escalation.

Update state phase to `verified_green`.

## Phase 5: Parallel Review

Dispatch M = N `pipeline-code-reviewer` agents (model: opus), one per chunk (1:1 mirror).

**See `phases/review_and_finalize.md` → Phase 5** for dispatch prompts and `review_<iteration>.md` artifact.

## Phase 6: Handle Verdicts

Re-dispatch rejected chunks only. Approved chunks are frozen.

**See `phases/review_and_finalize.md` → Phase 6** for decision tree and respawn loop (max 3).

Update state phase to `review_passed` when all PASS.

## Phase 7: Final Summary

Final verification, then write `summary.md` listing chunks, files, iterations, and deferred observations.

**See `phases/review_and_finalize.md` → Phase 7** for summary template. Update state status to `completed`.

## Error Handling

- **Ambiguous scope**: ask before Phase 1. **Empty scope**: report and exit.
- **No test framework**: ask user for command. **No linter**: note and skip.
- **Import graph fails**: fall back to directory-based chunking, flag in approval plan.
- **Write conflict**: re-run affected chunks sequentially. **Baseline red**: force user decision in Phase 2.5.

## State Management

After each phase, update `state.md` with current phase, iteration counts, files modified, and escalation notes. Allows resumption if interrupted.
