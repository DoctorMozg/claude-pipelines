---
name: combine
description: ALWAYS invoke when the user wants to synthesize or consolidate existing local research, task artifacts, or prior pipeline output into a unified report. Triggers: "synthesize what we learned", "combine our findings", "consolidate past research".
argument-hint: [output:<path>] [sources:<glob>] [scope:branch|global|working] [sections:<csv>] <task — what to synthesize>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Local Source Combination Pipeline

## Overview

You orchestrate a local-first synthesis that harvests prior pipeline output — `.mz/research/`, `.mz/task/*/`, `.mz/reports/`, `.mz/reviews/`, codebase files, and git history — and folds it into a unified report with task-adaptive sections (or user-supplied sections). Counterpart to `/deep-research`: that skill is web-first and starts from zero; this one assumes prior output exists and only consults the web to fill residual gaps behind an explicit approval gate.

## When to Use

Invoke when the user asks to synthesize, consolidate, or pull together knowledge that already lives on disk. Trigger phrases: "synthesize what we learned", "combine our findings", "consolidate past research", "pull together everything about X".

### When NOT to use

- Zero prior local research exists — use `/deep-research` instead.
- The user wants to understand how code works — use `/explain` instead.
- The user wants to verify a hypothesis or run exploratory tests — use `/investigate`. If the user then wants to synthesize prior `/investigate` output, `/combine` is the right follow-up.
- The user needs a fixed-template compliance report — use a dedicated audit skill.

## Input

- `$ARGUMENTS` — the task text plus any optional parameters: `output:<path>`, `sources:<glob>`, `scope:branch|global|working`, `sections:<csv>`. Remainder after parameter extraction is the task description.
- Example: `/combine sections:Context,Findings,Risks synthesize our findings on the auth refactor`.
- If empty or ambiguous, ask via AskUserQuestion. Never guess.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). The `scope:` parameter narrows **only the codebase lens file-list**, not the `.mz/` source harvest — prior research, reports, and task artifacts are always eligible regardless of scope.

| Mode      | Resolution                                          | Git command                                                                                |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `branch`  | Files changed on this branch vs base branch         | `git diff $(git merge-base HEAD <base>)..HEAD --name-only` (base: `main`, then `master`)   |
| `global`  | All source files in the repo                        | Honor `.gitignore`; apply standard exclusions (vendored, generated, lock files, >5000 LOC) |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`                |

**Default** (no `scope:` parameter): codebase lens derived from task-text file-name hints via Grep/Glob.

## Output Parameter

Extract `output:<path>` from `$ARGUMENTS` if present — overrides the default report path.

**Default**: `.mz/reports/combine_<YYYY_MM_DD>_<slug>.md`. On collision append `_v2`, `_v3` per Rule 11.

## Sections Parameter

Extract `sections:<comma-separated list>` from `$ARGUMENTS` if present. If provided, the report's top-level sections are taken **verbatim from the list, in the order given**. If absent, sections are derived from the task text — see `phases/synthesis.md §Phase 5`. Meta-sections (Timeline, Conflicts, Gaps, Sources, Methodology) are always appended regardless of branch.

## Constants

- `MAX_LENSES = 6` — hard cap on parallel lens agents in Phase 2 (Rule 13 wave cap).
- `TASK_ARTIFACT_STALE_DAYS = 30` — freshness cutoff for `.mz/task/*/` artifacts.
- `REPORT_STALE_DAYS = 60` — freshness cutoff for `.mz/reports/*` and `.mz/reviews/*`.
- `RESEARCH_STALE_DAYS = 90` — freshness cutoff for `.mz/research/*` deep-research reports.
- `MAX_GAP_FILL_WAVES = 1` — single-shot web gap-fill cap (prevents infinite loops, Rule 10).
- `TASK_DIR = .mz/task/` — working artifact root.
- `REPORT_DIR = .mz/reports/` — final report root.
- `RESEARCH_DIR = .mz/research/` — deep-research artifact root; primary source for the `research` lens.
- `MIN_TASK_QUERY_TOKENS = 5` — below this token count in the task text, Phase 0.2 fires a focusing question before any phase runs.

## Core Process

### Phase Overview

| #   | Phase                                   | Reference                                                      | Loop? |
| --- | --------------------------------------- | -------------------------------------------------------------- | ----- |
| 0   | Setup                                   | inline below                                                   | —     |
| 1   | Source Inventory and Lens Decomposition | `phases/inventory.md`                                          | —     |
| 1.5 | Decomposition Approval Gate             | inline stub + body in `phases/inventory.md §Phase 1.5 Gate`    | yes   |
| 2   | Parallel Lens Dispatch                  | `phases/lens_dispatch.md`                                      | —     |
| 3   | Cross-Reference Synthesis               | `phases/synthesis.md`                                          | —     |
| 3.5 | Gap-Fill Approval Gate (conditional)    | inline stub + body in `phases/synthesis.md §Phase 3.5 Gate`    | yes   |
| 4   | Web Gap-Fill (conditional)              | `phases/lens_dispatch.md §Phase 4: Web Gap-Fill (conditional)` | —     |
| 5   | Task-Adaptive Report Generation         | `phases/synthesis.md`                                          | —     |

Read the relevant phase file when you reach that phase. Do not read all phase files upfront.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration skill per Rule 17, not discipline. See Rule 17.

## Red Flags

- Inline `.mz/` reads from the orchestrator — only filenames and mtimes are allowed inline; file bodies belong in lens agents.
- More than `MAX_LENSES` lenses dispatched in a single wave.
- Web `pipeline-web-researcher` agent dispatched before Phase 3.5 approval.
- Fixed-template report produced when `sections:` was not explicitly supplied by the user.

## Verification

Before completing, output a visible block showing: task slug, lenses dispatched, gap-fill y/n, residual gaps count, absolute report path. Confirm the report file exists on disk.

## Phase 0: Setup

- **0.1 Parse arguments** — extract `output:`, `sources:`, `scope:`, and `sections:` from `$ARGUMENTS` (case-insensitive); remove each matched parameter from the argument text — the remainder is the task description.
- **0.2 Vague-task check** — count whitespace-separated tokens in the task text; if fewer than `MIN_TASK_QUERY_TOKENS`, or the task contains a banned token (`everything`, `all`, `whatever`), fire AskUserQuestion with a focusing prompt before proceeding. Never guess intent.
- **0.3 Derive task name** — format `combine_<slug>_<HHMMSS>` where slug is a snake_case summary of the task text (max 20 chars) and HHMMSS is current wall-clock time.
- **0.4 Create task directory and state** — `mkdir -p .mz/task/<task_name>/` and write `state.md` with fields: Status, Phase, Started, Task, Output, Lenses, Sections (source: `task-derived` | `user-supplied`).
- **0.5 Create task tracking** — use TaskCreate for each pipeline phase.
- **0.6 Transition** — read `phases/inventory.md` and proceed to Phase 1.

## Phase 1.5: Decomposition Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: the source inventory summary (bucket counts, stale-excluded count, unavailable buckets) and the proposed lens decomposition (3–6 lenses with names and file counts) from `inventory.md`. See `phases/inventory.md §Phase 1.5 Gate` for extended presentation content and feedback handling rules.

Use AskUserQuestion with:

```
Source inventory complete for "<task slug>". <N> lenses proposed: <lens names>. Full decomposition at .mz/task/<task_name>/inventory.md.

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update `state.md` phase to `decomposition_approved`, proceed to Phase 2 (`phases/lens_dispatch.md`).
- **"reject"** → update `state.md` to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → incorporate, re-run Phase 1.2/1.3 as needed, overwrite `inventory.md`, return to this gate, re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves. Never proceed without explicit approval.

## Phase 3.5: Gap-Fill Approval Gate (conditional)

If the residual gap list produced by Phase 3 is empty, skip this gate and jump to Phase 5.

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: the residual gap list (one bullet per gap with context) and the estimated cost (number of web `pipeline-web-researcher` agents to dispatch, capped at `MAX_LENSES`). See `phases/synthesis.md §Phase 3.5 Gate` for extended presentation content and merge rules.

Use AskUserQuestion with:

```
Synthesis left <N> residual gap(s): <short list>. Web gap-fill would dispatch <M> researcher agent(s).

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update `state.md` phase to `gapfill_approved`, proceed to Phase 4 (`phases/lens_dispatch.md §Phase 4`).
- **"reject"** → update `state.md` phase to `gapfill_declined`, skip to Phase 5 with gaps marked unresolved. Do not proceed to Phase 4.
- **Feedback** → incorporate (drop/merge/rewrite gaps), return to this gate, re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves or rejects. Never dispatch web researchers without explicit approval.

## Error Handling

- **Vague task** — Phase 0.2 fires the focusing question; do not advance until clarified.
- **Empty `.mz/`** — AskUserQuestion offering codebase-only mode or abort. Never silently degrade to `/deep-research`.
- **Lens agent returns `BLOCKED`** — escalate via AskUserQuestion, no auto-retry.
- **Lens agent returns `NEEDS_CONTEXT`** — single re-dispatch with the requested context, then escalate.
- **`MAX_GAP_FILL_WAVES` exhausted** — report residual gaps as unresolved in the final report; do not iterate.
- **Report collision** — append `_v2`, `_v3` per Rule 11.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with: current Phase, lenses dispatched / returned, residual gap count, gap-fill status, output path, and `sections_source` (`task-derived` | `user-supplied`).
