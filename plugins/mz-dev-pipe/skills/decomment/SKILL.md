---
name: decomment
description: ALWAYS invoke when the user wants to strip AI-flavored comments and docstrings from code. Triggers "decomment", "strip AI comments", "remove robotic comments". When NOT to use - markdown (use naturalize), full comment deletion, code refactor.
argument-hint: '[scope:branch|global|working] [path/glob override]'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

## Overview

`decomment` strips AI-flavored comments and docstrings from code files. The orchestrator resolves a file scope (branch diff by default), fans out `pipeline-decomment-proposer` Sonnet agents in parallel waves to identify high-confidence AI artifacts in comment regions only, aggregates every proposed before/after pair into a single diff, gates once for explicit user approval, and applies the approved edits via the Edit tool. The skill never touches executable code, never modifies string literals, and preserves load-bearing comments (workaround notes, tooling directives, license headers, docstring fields).

## When to Use

- Cleaning AI residue from a feature branch before merge.
- Removing robotic section banners, phase headers, and restate-the-signature docstrings from generated code.
- Trigger phrases: "decomment", "strip AI comments from my branch", "remove robotic comments", "clean LLM comments from code".

### When NOT to use

- Markdown or prose files — use `naturalize`.
- Deleting ALL comments wholesale — this skill targets AI artifacts only, not every comment.
- Code refactor or function-body rewriting — comment-region edits only.
- Executable code rewriting — out of scope; the proposer tokenizes per-language and never edits non-comment regions.
- String-literal cleanup — strings are preserved by the tokenizer.

## Constants

- **PROJECT_ROOT**: resolved once in setup with `echo "${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"`; expand `<PROJECT_ROOT>` to it in every command and agent prompt.
- **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`. Skill and phase files write `<PLUGIN_ROOT>/...` because files opened with Read get no variable substitution; expand it to this absolute path before reading a file, running a command, or passing a path to an agent.

## Core Process

### Phase Overview

| #   | Phase         | File                    | Goal                                                                                 | Artifact                                                        |
| --- | ------------- | ----------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| 0   | Setup         | inline SKILL.md         | Parse args, resolve scope, detect git base, write `state.md`, resume-check           | `state.md`                                                      |
| 1   | Scan          | `phases/scan.md`        | Enumerate target files via scope, filter to code extensions, skip codegen            | `scope_files.txt`, `candidates.md`                              |
| 2   | Propose       | `phases/dispatch.md`    | Dispatch `pipeline-decomment-proposer` in waves of `MAX_PARALLEL`, collect proposals | `dispatch_plan.md`, `proposals/<slug>.md`                       |
| 3   | Consolidate   | `phases/consolidate.md` | Merge proposals, validate non-overlap, build diff for review                         | `diff.md`, `edits.json`, `skipped.md`, `apply_warnings.md`      |
| 3.5 | Gate (single) | inline SKILL.md         | Two-surface plan gate: verbatim diff as a plan message + AskUserQuestion selector    | `state.md` (`## Decisions` entry, or `Status: aborted_by_user`) |
| 4   | Apply         | `phases/apply.md`       | Apply approved edits via Edit tool, record success/failure                           | `apply_log.md`, `apply_failures.md`, `summary.md`               |

### Constants

| Constant                      | Value                                                         | Used in                                                                 |
| ----------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `MAX_PARALLEL`                | 6                                                             | Phase 2 wave size                                                       |
| `MAX_FILE_LOC`                | 4000                                                          | Phase 1 — files larger than this get an `oversize` row in candidates.md |
| `DIFF_DISPLAY_LINES_PER_EDIT` | 40                                                            | Phase 3 — truncation per `old_string`/`new_string` in diff.md           |
| `LICENSE_HEADER_SCAN_LINES`   | 30                                                            | Proposer — lines from file top scanned for license markers              |
| `CODEGEN_CONTENT_SCAN_LINES`  | 50                                                            | Phase 1 — lines scanned for `Generated by` / `DO NOT EDIT`              |
| `task_dir`                    | `<PROJECT_ROOT>/.mz/task/<YYYY_MM_DD>_decomment_<slug>/`      | All phases                                                              |
| `proposals_dir`               | `${task_dir}proposals/`                                       | Phase 2 output, Phase 3 input                                           |
| `summary_path`                | `<PROJECT_ROOT>/.mz/reports/<YYYY_MM_DD>_decomment_<slug>.md` | Phase 4 final summary                                                   |
| `SKILL_DIR`                   | `${CLAUDE_SKILL_DIR}`                                         | Phase files write `<SKILL_DIR>/...`; expand to this absolute path first |

### Phase 0 — Setup

1. Resolve `PROJECT_ROOT` with the command in Constants, before any `cd` or worktree switch, and use it for every `.mz/` path below.
1. Parse `$ARGUMENTS` for a `scope:` token (case-insensitive: `branch` | `global` | `working`). Default is `branch`. Treat every remaining token as a path or glob override and record it for Phase 1.
1. Compute `task_name = <YYYY_MM_DD>_decomment_<slug>`. Slug rules: `branch_diff` for the default branch scope, `global` for global scope, `working` for working-tree scope, or the first 20 chars of the explicit path token when a path override is supplied. Same-day collisions append `_v2`, `_v3`.
1. **Resume check** (before creating the task directory): follow `<PLUGIN_ROOT>/shared/resume-protocol.md`, "On entry". A `complete`, `completed` or `aborted_by_user` file starts a `_vN`. A `pending`, `running`, `blocked` or `failed` file gets the resume gate. When the run is unattended or nobody can answer, report the path, `Status` and `what_remains`, and stop.
1. Create `<PROJECT_ROOT>/.mz/task/<task_name>/` and `<PROJECT_ROOT>/.mz/task/<task_name>/proposals/`.
1. Write `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`: `schema_version: 2`, `Status: running`, `Phase: 0`, `PhaseName: setup`, `Started: <ISO timestamp>`, `Iteration: 1`, `FilesWritten: []`, `phase_complete: false`, `what_remains: []`, `scope_mode: <mode>`, `scope_files: []`, `proposals_done: 0`, `proposals_skipped: 0`, `files_with_edits: 0`, `total_edits: 0`, `edits_applied: 0`, `edits_failed: 0`. Run `printenv MZ_DEV_PIPE_AUTO_APPROVE` once and record `unattended: true` or `unattended: false` in `state.md`.
1. Proceed to Phase 1 (Read `phases/scan.md` and execute).

### Phase 3.5 — Approval gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

See `<PLUGIN_ROOT>/shared/approval-gate.md` for the canonical two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format used below.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/diff.md` with the Read tool and capture its full contents into context.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: diff gate]`; `Status` stays `running`.

**Surface 1 — emit the plan message.** Output the diff verbatim as a normal markdown chat message. Emit the full verbatim contents of `<PROJECT_ROOT>/.mz/task/<task_name>/diff.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Cleanup plan ready for review — decomment

Scanned <N> code files in scope; the proposers emitted <M> edits across <K> files. The diff below shows every old/new pair the orchestrator will apply.

<verbatim contents of diff.md>

---
**Approve** → apply every edit in edits.json (Phase 4)  ·  **Reject** → mark task aborted, no file is touched  ·  reply with feedback to revise

Approve cost (estimated): <M> Edit calls × ~0 agents ≈ ~$0.00 (apply phase runs no LLMs)
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the diff in the question body, it lives in the plan message above:

- question: `The proposed edits above are ready for review.`
- header: `Diff`
- options: **Approve** — apply every edit in edits.json (Phase 4) · **Reject** — mark task aborted, no file is touched

Response handling:

- **Approve** → add `- diff approved: .mz/task/<task_name>/diff.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, and proceed to Phase 4.
- **Reject** → update `state.md` to `aborted_by_user` and stop. No file is touched.
- **Any other reply (feedback)** → parse skip directives into an exclusion list (edit ids and/or file paths), regenerate `diff.md` and `edits.json` without the excluded edits or files, and if the feedback narrows the file set re-run Phase 1. Then return to this gate, re-read `diff.md`, and re-emit the entire plan message from scratch with the full new contents. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 4 without explicit approval.
- **Unattended** (`unattended: true` in `state.md`) → `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode": emit Surface 1, skip Surface 2, continue as on Approve, and log the gate in chat, under `## Auto-approvals`, in the journal and in the final report.
- **No answer** → set `Status: blocked`, keep `awaiting approval: diff gate`, stop. A missing answer is never approval.

Single gate, two paths only — no Apply/Skip/Diff submenu inside the AskUserQuestion call.

## Common Rationalizations

| Rationalization                                                         | Rebuttal                                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Just strip everything aggressive, I'll catch over-strips at the gate." | "The gate shows you each `old_string`/`new_string` pair, not the surrounding 50 lines of context. Aggressive mode plus volume blinds the gate. Conservative default is the gate's force multiplier, not its competitor."                                                               |
| "These banner dividers are obviously AI — strip them all."              | "Banner dividers around a workaround note are load-bearing visual structure. The preserve-zone (WHY tokens, RFC refs, dates, URLs) decides per-block, not per-pattern. A blanket strip rule deletes legitimate comments."                                                              |
| "Skip the gate, the proposer is good enough."                           | "The proposer matches patterns; only the user can confirm a comment isn't load-bearing in the project's actual context. Unattended mode (`MZ_DEV_PIPE_AUTO_APPROVE=1`) skips the selector and logs every skipped gate, but the default is single-gate-required and that is not a bug." |
| "Verbose docstrings restate the signature — just delete them all."      | "Five conditions must hold simultaneously before docstring deletion is safe: full typing, AI opener phrase, no tooling fields, no non-signature identifiers, all content words overlap with name/params. Partial matches preserve."                                                    |

## State Management

Each phase updates `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` per the per-phase steps in its phase file; never rely on conversation memory for cross-phase state.

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a verification gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade.

## References

- `<PLUGIN_ROOT>/shared/scope-parameter.md` — scope modes + git commands
- `<PLUGIN_ROOT>/shared/approval-gate.md` — two-surface gate pattern
- `<PLUGIN_ROOT>/shared/state-schema.md` — state.md schema
- `<PLUGIN_ROOT>/shared/resume-protocol.md` — resume entry contract
- `<PLUGIN_ROOT>/shared/agent-status-protocol.md` — four-status STATUS vocabulary
- `references/per-language-comment-syntax.md` — language-specific comment tokens + preserve markers (read by proposer)
