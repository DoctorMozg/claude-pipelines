---
name: dev-optimize
description: Map-reduce optimization pipeline — scans a scope, builds an import graph, dispatches parallel optimizers (1-6) with mirrored reviewers, iterates on rejections. Provide scope as the argument.
argument-hint: [scope:branch|global|working] <scope: glob, directory, git range, or free-text description>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Code Optimization Pipeline

You orchestrate a multi-agent optimization pass over existing code. You take a scope, build an import-graph-based chunking, dispatch parallel `pipeline-optimizer` agents, then dispatch mirrored `pipeline-code-reviewer` agents per chunk. On rejection, you respawn only the rejected chunks' optimizers with feedback and iterate. You run tests and linters after each batch and auto-fix any regressions before entering review.

## Input

- `$ARGUMENTS` — The scope. Any one of:
  - **Glob pattern**: `"src/**/*.py"`
  - **Directory**: `"src/auth/"`
  - **Git range**: `"origin/main..HEAD"` (files changed on this branch)
  - **Free-text description**: `"the authentication module"` (interpreted by a researcher agent)

Auto-detect the form. If ambiguous or empty, ask the user to clarify — do not guess.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before applying the detection logic above.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, files >5000 LOC).                                                                                     |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): use the existing scope detection logic (glob / directory / git range / free-text).

If `scope:` is given alongside an explicit scope argument (e.g., `scope:branch "src/auth/"`), the `scope:` parameter provides the file list and the explicit argument acts as an additional filter (intersection).

## Core Principles

1. **Behavior preservation is non-negotiable.** Optimization must not change test-observable behavior. Tests and linters run between every batch and every iteration.
1. **Parallel where safe, sequential where necessary.** Import-graph chunks are designed to minimize cross-cutting. Cross-chunk or out-of-scope edits are permitted when required for correctness, but must be reported and conflicts must be resolved.
1. **Ask when unclear.** If scope is ambiguous, chunks look wrong, a reviewer verdict is borderline, or test regressions can't be root-caused — stop and ask the user via AskUserQuestion. Do not plow ahead.

## Constants

- **MAX_OPTIMIZERS**: 6 — hard cap on parallel optimizer agents
- **MAX_REVIEWERS**: 6 — hard cap on parallel reviewer agents (always equals optimizer count, 1:1 mirror)
- **MAX_REVIEW_ITERATIONS**: 3 — max rejection rounds before escalating
- **MAX_FIX_ATTEMPTS**: 3 — max inner-fix-loop attempts in Phase 4 before escalating
- **TASK_DIR**: `.mz/task/` — all artifacts under `.mz/task/<task_name>/`

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

______________________________________________________________________

## Phase 0: Setup

### 0.1 Derive task name

From the scope argument, derive a short snake_case name (max 30 chars).
Examples:

- `"src/auth/"` → `optimize_src_auth`
- `"origin/main..HEAD"` → `optimize_branch_delta`
- `"the authentication module"` → `optimize_auth_module`

### 0.2 Create task directory

```bash
mkdir -p .mz/task/<task_name>
```

### 0.3 Initialize state file

Write `.mz/task/<task_name>/state.md`:

```markdown
# Optimize: <scope summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Review iterations**: 0
- **Fix attempts**: 0
- **Files in scope**: 0 (pending scan)
- **Chunks**: 0 (pending scan)
```

### 0.4 Create task tracking

Use TaskCreate to create one top-level task per pipeline phase so the user can track progress.

______________________________________________________________________

## Phase 1: Scan & Chunk

Resolves the input to a concrete file list, dispatches a `pipeline-researcher` agent (model: sonnet) to build the import graph, then groups files into 1-6 chunks using strongly-connected components and module boundaries.

**See `phases/scan_and_plan.md` → Phase 1** for scope resolution, graph construction, chunking algorithm, and the `.mz/task/<task_name>/scan.md` artifact.

Update state file phase to `scanned`.

______________________________________________________________________

## Phase 2: Baseline Snapshot

Runs the project's tests and linters once to capture the pre-optimization state. Required before any optimizer touches code — otherwise regressions can't be detected.

**See `phases/scan_and_plan.md` → Phase 2** for tooling detection and the `.mz/task/<task_name>/baseline.md` artifact.

Update state file phase to `baseline_captured`.

______________________________________________________________________

## Phase 2.5: User Approval Gate

After Phases 1 and 2 complete, **this orchestrator** (not a subagent) must present an **optimization plan** to the user via AskUserQuestion. This step is interactive and must not be delegated.

The optimization plan must include:

1. **Resolved scope**: exact file list (collapsed by directory if > 20 files)
1. **Chunk breakdown**: N chunks with per-chunk file list and rationale ("SCC of 4 mutually-imported modules", "isolated utility file", etc.)
1. **Optimizer count**: N (1-6)
1. **Reviewer count**: M = N (1:1 mirror)
1. **Baseline status**: tests PASS/FAIL, lint CLEAN/WARNINGS/ERRORS
1. **Risks flagged**: files the researcher marked as high-coupling, tests that were already failing, chunks likely to require cross-chunk edits

Use AskUserQuestion with:

```
The optimization plan is ready. Please review and approve:

<plan contents>

Reply 'approve' to proceed, or provide feedback for changes (e.g. exclude a file, adjust chunking, change chunk count).
```

**If the user provides feedback**: apply the changes (re-chunk, exclude files, etc.), overwrite `scan.md` and the in-memory plan, and re-present. Do not run a separate plan-review agent — the user's word is final.

**If baseline was RED** (tests already failing OR lint errors before Phase 3): include that prominently in the plan and ask the user explicitly whether to proceed, abort, or run `polish-pipeline` first. Do not default to proceeding on a red baseline.

Update state file phase to `plan_approved`.

______________________________________________________________________

## Phase 3: Parallel Optimization

Dispatches N `pipeline-optimizer` agents (model: opus) in a single-message parallel fan-out, one per chunk. Each optimizer's prompt carries its chunk's file list, the baseline status, and the scoping rules (strict within-chunk ownership, narrow exception for cross-chunk or out-of-scope edits required for correctness).

**See `phases/optimize_and_verify.md` → Phase 3** for dispatch prompts, conflict detection, and the `.mz/task/<task_name>/optimization_<iteration>.md` artifact.

______________________________________________________________________

## Phase 4: Verify & Auto-Fix

Re-runs tests and linters after the optimization batch. Must restore green state before Phase 5 — never enter review on a red build.

**See `phases/optimize_and_verify.md` → Phase 4** for the inner fix loop with `pipeline-coder` dispatch, max `MAX_FIX_ATTEMPTS = 3` attempts, and escalation logic.

Update state file phase to `verified_green`.

______________________________________________________________________

## Phase 5: Parallel Review

Dispatches M = N `pipeline-code-reviewer` agents (model: opus) in a single message, one per chunk. Each reviewer validates its chunk against the behavior-preservation contract.

**See `phases/review_and_finalize.md` → Phase 5** for dispatch prompts and the `.mz/task/<task_name>/review_<iteration>.md` artifact.

______________________________________________________________________

## Phase 6: Handle Verdicts

Decide whether to finalize, iterate, or escalate based on merged reviewer verdicts.

**See `phases/review_and_finalize.md` → Phase 6** for the decision tree, selective re-dispatch of rejected chunks only (approved chunks are frozen), borderline-verdict handling, and escalation after `MAX_REVIEW_ITERATIONS = 3`.

Update state file phase to `review_passed` when all chunks PASS.

______________________________________________________________________

## Phase 7: Final Summary

Final verification pass, then writes `.mz/task/<task_name>/summary.md` listing chunks, files changed, iterations used, and deferred cross-chunk observations for future cleanup.

**See `phases/review_and_finalize.md` → Phase 7** for the summary template and user report.

Update state file status to `completed`.

______________________________________________________________________

## Error Handling

- **Ambiguous scope**: ask the user to narrow it before Phase 1. Never guess the interpretation.
- **Empty resolved scope**: if the file list is empty after filtering, report and exit — nothing to do.
- **No test framework detected**: ask the user for a verification command. Do not proceed without one.
- **No linter detected**: note it and skip lint checks; don't block.
- **Import graph construction fails**: fall back to directory-based chunking and flag the fallback in the approval plan.
- **Parallel write conflict**: if two optimizers in the same wave edited the same file via cross-chunk exception, mark the conflict in the optimization report and re-run the affected chunks sequentially in the next iteration.
- **Baseline already red**: surface in Phase 2.5 and force a user decision. Do not silently optimize on top of broken code.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Review iteration count
- Fix-attempt count
- Cumulative list of files modified
- Any escalation notes

This allows the pipeline to be resumed if interrupted.
