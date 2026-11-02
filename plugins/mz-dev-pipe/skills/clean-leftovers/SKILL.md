---
name: clean-leftovers
description: 'Removes AI-run residue, code included: signatures, phase markers, stubs. Use when the user says "clean leftovers", "remove AI markers" or "clean up after the pipeline". Not for comment-only tidying (use decomment) or refactors (use cleanup).'
argument-hint: '[scope:branch|global|working] [path or glob]'
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
---

# Pipeline Leftover Cleanup

## Overview

Removes AI-generation leftover artifacts from code: AI signatures and tool watermarks, pipeline phase markers, planning/generation-process comments, WHAT-not-WHY comments, and dead code or half-implementations. Detect → approval gate → cleanup → re-verify. Mirrors `/naturalize`, but operates on source files instead of prose.

## When to Use

Sweeping a branch or working tree for the wider residue of an AI run (signatures, phase and plan markers, half-built stubs, dead code), code included, e.g. before a PR to remove provenance leaks.

### When NOT to use

- Comment- and docstring-only tidying that must leave executable code untouched — use `/decomment`.
- Prose rewriting (AI-style writing patterns in narrative markdown) — use `/naturalize`.
- Generic code-quality cleanup with no AI-artifact focus — use `/cleanup`.
- Fixing failing tests or completing partial features — use `/polish`.
- Hunting bugs — use `/audit`.

## Input

`$ARGUMENTS` — optional `scope:` mode plus an optional path or glob. Empty input is valid; defaults apply (`scope:working`, no path filter). Ambiguous combinations (e.g. `scope:global` plus a narrow glob) ask via AskUserQuestion before Phase 1.

## Scope Parameter

See `<PLUGIN_ROOT>/shared/scope-parameter.md` for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- **Default** (no `scope:`): `working` — uncommitted changes are the highest-signal target for pipeline leftovers.
- `scope:` controls **which files agents may edit**. The detection scan and the verification re-scan respect the same scope.
- Markdown files under `docs/`, `guidelines/`, the repo-root `README.md`, and this skill's own `references/` directory are excluded from edits by default — they legitimately quote AI artifacts as examples. Override with an explicit path argument.

## Constants

- **MAX_FIX_ITERATIONS**: 3 — cleanup loops if residuals remain after verification.
- **MAX_FILES_PER_DISPATCH**: 25 — per cleaner-agent file budget.
- **MAX_PARALLEL_AGENTS**: 6 — concurrent cleaner dispatches per wave.
- **WHAT_WHY_SIMILARITY_THRESHOLD**: 0.7 — token-overlap threshold for flagging WHAT-not-WHY candidates.
- **PROJECT_ROOT**: resolved once in setup with `echo "${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"`; expand `<PROJECT_ROOT>` to it in every command and agent prompt.
- **TASK_DIR**: `<PROJECT_ROOT>/.mz/task/`
- **REPORT_DIR**: `<PROJECT_ROOT>/.mz/reports/`
- **SKILL_DIR**: `${CLAUDE_SKILL_DIR}`. Phase files write `<SKILL_DIR>/...` because files opened with Read get no variable substitution; expand it to this absolute path before reading a file, running a command, or passing a path to an agent.
- **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`. Skill and phase files write `<PLUGIN_ROOT>/...` because files opened with Read get no variable substitution; expand it to this absolute path before reading a file, running a command, or passing a path to an agent.

## Core Process

### Phase Overview

| #   | Phase                 | File                     |
| --- | --------------------- | ------------------------ |
| 0   | Setup                 | inline below             |
| 1   | Research (mandatory)  | `phases/research.md`     |
| 2   | Detection             | `phases/detection.md`    |
| 2.5 | Approval gate         | inline below             |
| 3   | Cleanup execution     | `phases/cleanup.md`      |
| 4   | Verification + report | `phases/verification.md` |

Read the relevant phase file when you reach that phase. Do not pre-load all of them.

### Phase 0: Setup

1. **Resolve project root** — resolve `PROJECT_ROOT` with the command in Constants, before any `cd` or worktree switch, and use it for every `.mz/` path below.
1. **Parse arguments** — extract `scope:` (default `working`); the remaining text is an optional path or glob filter.
1. **Resolve scope** — apply the scope reference above to get the concrete file list, and save it to `<PROJECT_ROOT>/.mz/task/<task_name>/scope_files.txt` once the task directory exists. Skip excluded markdown directories unless explicitly requested.
1. **Task name** — `<YYYY_MM_DD>_clean_leftovers_<slug>` where `<slug>` is snake_case of scope mode + first 3 words of any path filter (max 20 chars). On same-day collision append `_v2`, `_v3`.
1. **Resume check** (before creating the task directory): follow `<PLUGIN_ROOT>/shared/resume-protocol.md`, "On entry". A `complete`, `completed` or `aborted_by_user` file starts a `_vN`. A `pending`, `running`, `blocked` or `failed` file gets the resume gate. When the run is unattended or nobody can answer, report the path, `Status` and `what_remains`, and stop.
1. **Create task dir & state** — `<PROJECT_ROOT>/.mz/task/<task_name>/`. Write `state.md` there per `<PLUGIN_ROOT>/shared/state-schema.md`: first line `schema_version: 2`, required keys (`Status`, `Phase`, `Started`, `Iteration` 0, `FilesWritten`, `phase_complete: false`, `what_remains: []`), plus skill-specific (`scope`, `files_in_scope`, `categories_to_clean`). Run `printenv MZ_DEV_PIPE_AUTO_APPROVE` once and record `unattended: true` or `unattended: false` in `state.md`.
1. **Emit a visible setup block** — task name, scope, file count, exclusions. Read `phases/research.md` and proceed to Phase 1.

### Phase 2.5: Approval Gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

See `<PLUGIN_ROOT>/shared/approval-gate.md` for the two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/detection.md` with the Read tool. Capture the full file contents (per-category hit lists with file:line citations, severity classification, and the proposed cleanup plan) into context.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: detection gate]`; `Status` stays `running`.

Compute `<N>` as `ceil(<files_in_scope> / MAX_FILES_PER_DISPATCH)` plus the verification re-scan, capped at `MAX_PARALLEL_AGENTS × MAX_FIX_ITERATIONS`. Use `<PLUGIN_ROOT>/shared/approval-gate.md` to convert to a dollar estimate.

**Surface 1 — emit the plan message.** Output the detection report verbatim as a normal markdown chat message. Emit the full verbatim contents of `<PROJECT_ROOT>/.mz/task/<task_name>/detection.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Detection ready for review — clean-leftovers

<verbatim contents of detection.md>

---
**Approve** → proceed to Phase 3 (cleanup) using the proposed plan  ·  **Reject** → mark task aborted, no files edited  ·  reply with feedback to revise

Approve cost (estimated): <N> agents × ~20k tokens ≈ ~$<Y.YY> on Opus
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the detection report in the question body:

- question: `The detection report above is ready for review. Approve to proceed, or Reject to abort — reply with feedback to revise.`
- header: `Detection`
- options: **Approve** — proceed to Phase 3 (cleanup) · **Reject** — abort, no files edited

**Response handling**:

- **Approve** → add `- detection approved: .mz/task/<task_name>/detection.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, set `Phase: detection_approved`, and proceed to Phase 3.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → adjust the plan, overwrite `detection.md`. Return to Surface 1, re-read `<PROJECT_ROOT>/.mz/task/<task_name>/detection.md`, and re-emit the entire plan message from scratch — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.
- **Unattended** (`unattended: true` in `state.md`) → `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode": emit Surface 1, skip Surface 2, continue as on Approve, and log the gate in chat, under `## Auto-approvals`, in the journal and in the final report.
- **No answer** → set `Status: blocked`, keep `awaiting approval: detection gate`, stop. A missing answer is never approval.

## Common Rationalizations

| Rationalization                             | Rebuttal                                                                         |
| ------------------------------------------- | -------------------------------------------------------------------------------- |
| "the AI signatures are harmless"            | "they leak provenance, embarrass on review, and look amateurish in shipped code" |
| "WHAT comments are still informative"       | "they desync on every edit; the reader still has to read the code to trust them" |
| "the phase markers don't run, so it's fine" | "they confuse future readers and waste review time"                              |
| "research is overkill for this"             | "AI tool watermarks shift every few months; the embedded list goes stale"        |
| "skip the approval gate for speed"          | "WHAT-not-WHY false positives are costly; review preserves real comments"        |

## Red Flags

- Skipped the mandatory research pass.
- Deleted a comment that captured a real WHY (regulatory note, perf workaround, surprising-behavior callout).
- Modified prose markdown files that legitimately quote AI artifacts as examples (guidelines, this skill's own references).
- Removed dead-looking code that was a documented public API stub for downstream consumers.
- Committed without re-running the linter after edits.

## Verification

Output the verification block defined in `phases/verification.md`: task dir, report path, scope, per-category artifact counts, iterations, linter status, residuals. Any non-empty residual list with `Iterations: MAX_FIX_ITERATIONS` blocks completion — escalate via AskUserQuestion.

## References

- `${CLAUDE_SKILL_DIR}/references/artifact-catalog.md`: patterns for the five leftover categories (AI signatures, phase markers, planning comments, WHAT-not-WHY candidates, dead code). Grep it per category (`# Category A:` to `# Category E:`) in Phase 2 and while cleaning; do not read it whole.

## Error Handling

- Empty scope → report and exit cleanly; do not dispatch agents.
- Research dispatch fails twice → continue with embedded catalog and flag in the report.
- Cleaner `BLOCKED` → preserve file unmodified, escalate via AskUserQuestion. Cleaner `NEEDS_CONTEXT` → fill missing context, re-dispatch.
- Linter not detected → record `n/a` and continue; do not silently skip. Update `state.md` before and after every agent dispatch.

## State Management

After each phase update `state.md`: `Status`, `Phase`, `Iteration` (cleanup loop), `FilesWritten` (cumulative), `categories_remaining` (categories with residuals after latest verification scan). Never rely on conversation memory for cross-phase state.

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a verification gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, in the form `- (review|failure|correction|change) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`.
