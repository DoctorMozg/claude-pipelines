---
name: optimize
description: ALWAYS invoke when the user wants to optimize, clean up, or reduce complexity in existing code. Triggers: "optimize X", "clean up", "refactor", "remove dead code". When NOT to use: fixing failing tests (use polish), bug hunt (use debug or audit).
argument-hint: [scope:branch|global|working] <scope: glob, directory, git range, or free-text description>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Code Optimization Pipeline

## Overview

Orchestrates a multi-agent optimization pass over existing code. Builds import-graph-based chunking, dispatches parallel `pipeline-optimizer` agents with mirrored `pipeline-code-reviewer` agents per chunk. On rejection, respawn rejected chunks only. Tests and linters run after each batch.

## When to Use

- User wants to clean up, reduce complexity, or eliminate dead code.
- Triggers: "optimize X", "clean up", "refactor", "reduce complexity", "remove dead code".
- Scope spans multiple files and benefits from parallel chunked cleanup.

### When NOT to use

- Failing tests that need fixing — use `polish`.
- Failing tests with a known root cause — use `debug` first, then `optimize` on the fixed code.
- Code that passes metrics but has UI/UX or test-quality issues — use `polish`.
- Known bug investigation — use `debug`.
- Bug and security hunt across lenses — use `audit`.
- Impact analysis before a refactor — use `blast-radius`.

## Input

- `$ARGUMENTS` — The scope: glob (`"src/**/*.py"`), directory (`"src/auth/"`), git range (`"origin/main..HEAD"`), or free-text (`"the authentication module"`). Auto-detect form. If ambiguous or empty, ask — do not guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default** (no `scope:`): use existing detection (glob / directory / git range / free-text).
- If `scope:` is given alongside an explicit argument, they **intersect**.

## Core Principles

1. **Behavior preservation is non-negotiable.** Tests and linters run between every batch.
1. **Parallel where safe, sequential where necessary.** Ask when unclear.

## Constants

- **MAX_OPTIMIZERS**: 6 | **MAX_REVIEWERS**: 6 | **MAX_REVIEW_ITERATIONS**: 3 | **MAX_FIX_ATTEMPTS**: 3 | **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

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

### Phase 0–2: Setup, Scan & Baseline

- **Phase 0 — Setup**: derive `optimize_<slug>_<HHMMSS>`, create `.mz/task/<task_name>/`, write `state.md` (Status, Phase, Started, `review_iteration: 0`, Fix attempts, Files in scope, Chunks). The explicit `review_iteration: 0` initialization allows the counter to be restored from `state.md` after context compaction. TaskCreate per phase.
- **Phase 1 — Scan & Chunk**: resolve to file list, build import graph, group into 1-6 chunks (SCCs + module boundaries). See `phases/scan_and_plan.md` → Phase 1. Update state to `scanned`.
- **Phase 2 — Baseline Snapshot**: run tests and linters to capture pre-optimization state. Required before optimizers touch code. See `phases/scan_and_plan.md` → Phase 2. Update state to `baseline_captured`.

### Phase 2.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/scan.md` with the Read tool. Capture the full file contents (resolved scope, chunk breakdown with rationale, optimizer/reviewer counts, baseline status, flagged risks) into context. **If baseline was RED**: ensure the RED status is preserved verbatim and prominent in what you present.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `scan.md`. Never substitute a path, status summary, line count, or `<plan contents>` placeholder — the user must review the actual plan in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Approval Gate — Optimization Plan Review**
Your scope has been scanned, chunked, and baselined. Review the plan below: N chunks, M files affected, baseline test/lint status shown.

- **Approve** → proceed to Phase 3 (parallel optimization)
- **Reject** → mark task aborted, no files written
- **Feedback** → apply changes to scan.md, re-present via AskUserQuestion
```

Invoke AskUserQuestion with this body (where `<verbatim scan.md contents>` is replaced by the bytes you just read):

```
The optimization plan is ready. Please review and approve:

<verbatim scan.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
(e.g. exclude a file, adjust chunking, change chunk count).
```

**Response handling**:

- **"approve"** → proceed to Phase 3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → apply changes, overwrite `scan.md`, return to this gate, re-read `scan.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.

### Phase 3: Parallel Optimization

Dispatch N `pipeline-optimizer` agents (model: opus) in a single message, one per chunk. See `phases/optimize_and_verify.md` → Phase 3.

### Phase 4: Verify & Auto-Fix

Re-run tests/linters; restore green before Phase 5. See `phases/optimize_and_verify.md` → Phase 4. Update state to `verified_green`.

### Phase 5: Parallel Review

Dispatch M = N `pipeline-code-reviewer` agents (opus), 1:1 per chunk. See `phases/review_and_finalize.md` → Phase 5.

### Phase 6: Handle Verdicts

Re-dispatch rejected chunks only. Approved chunks frozen. See `phases/review_and_finalize.md` → Phase 6. Update state to `review_passed` when all PASS.

### Phase 7: Final Summary

Final verification, then write `summary.md` listing chunks, files, iterations, deferred observations. See `phases/review_and_finalize.md` → Phase 7. Update state to `completed`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.
Reference files: grep `references/dead-code-detection-patterns.md` for per-language detection patterns — do not load the entire file.

## Common Rationalizations

| Rationalization                                  | Rebuttal                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------ |
| "dead code is harmless, leave it"                | "dead code accelerates context decay and hides the live code"            |
| "this loop is fine"                              | "hot-path loops are the 5% of code that is 80% of CPU time"              |
| "premature optimization is the root of all evil" | "so is late optimization of a known hot path; profile before you decide" |

## Red Flags

- Dead code was left in place to "minimize diff".
- The hot path was optimized without a profiler capture first.
- No before/after benchmark was captured when claiming a perf win.

## Verification

Output the final `summary.md` block: chunks touched, files modified, baseline vs post-optimization test/lint status, review iterations, and deferred observations.

## Error Handling

- **Ambiguous scope**: ask before Phase 1. **Empty scope**: report and exit.
- **No test framework**: ask user for command. **No linter**: note and skip.
- **Import graph fails**: fall back to directory-based chunking, flag in approval plan.
- **Write conflict**: re-run affected chunks sequentially. **Baseline red**: force user decision in Phase 2.5.

## State Management

After each phase, update `state.md` with current phase, iteration counts, files modified, and escalation notes. Allows resumption if interrupted.
