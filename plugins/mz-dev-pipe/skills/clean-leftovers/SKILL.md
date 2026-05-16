---
name: clean-leftovers
description: "ALWAYS invoke when the user wants to remove AI-generation leftovers from code. Triggers: 'clean leftovers', 'remove AI markers', 'strip phase comments', 'clean up after the pipeline', 'de-AI the code'. When NOT to use: prose rewriting (use /naturalize), general code quality cleanup (use /cleanup)."
argument-hint: '[scope:branch|global|working] [path or glob]'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
---

# Pipeline Leftover Cleanup

## Overview

Removes AI-generation leftover artifacts from code: AI signatures and tool watermarks, pipeline phase markers, planning/generation-process comments, WHAT-not-WHY comments, and dead code or half-implementations. Detect → approval gate → cleanup → re-verify. Mirrors `/naturalize`, but operates on source files instead of prose.

## When to Use

- Branch or working tree contains pipeline-run leftovers (Phase markers, AI signatures, planning comments, half-finished stubs).
- Pre-PR sweep to remove provenance leaks and amateur-looking generation artifacts before review.
- Triggers: "clean leftovers", "remove AI markers", "strip phase comments", "clean up after the pipeline", "de-AI the code".

### When NOT to use

- Prose rewriting (AI-style writing patterns in narrative markdown) — use `/naturalize`.
- Generic code-quality cleanup with no AI-artifact focus — use `/cleanup`.
- Fixing failing tests or completing partial features — use `/polish`.
- Hunting bugs — use `/audit`.

## Input

`$ARGUMENTS` — optional `scope:` mode plus an optional path or glob. Empty input is valid; defaults apply (`scope:working`, no path filter). Ambiguous combinations (e.g. `scope:global` plus a narrow glob) ask via AskUserQuestion before Phase 1.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- **Default** (no `scope:`): `working` — uncommitted changes are the highest-signal target for pipeline leftovers.
- `scope:` controls **which files agents may edit**. The detection scan and the verification re-scan respect the same scope.
- Markdown files under `docs/`, `guidelines/`, the repo-root `README.md`, and this skill's own `references/` directory are excluded from edits by default — they legitimately quote AI artifacts as examples. Override with an explicit path argument.

## Constants

- **MAX_FIX_ITERATIONS**: 3 — cleanup loops if residuals remain after verification.
- **MAX_FILES_PER_DISPATCH**: 25 — per cleaner-agent file budget.
- **MAX_PARALLEL_AGENTS**: 6 — concurrent cleaner dispatches per wave.
- **WHAT_WHY_SIMILARITY_THRESHOLD**: 0.7 — token-overlap threshold for flagging WHAT-not-WHY candidates.
- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`

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

1. **Resume check** — apply [`skills/shared/resume-protocol.md`](../shared/resume-protocol.md). If `state.md` exists with `Status: running | failed`, present the Resume gate.
1. **Parse arguments** — extract `scope:` (default `working`); the remaining text is an optional path or glob filter.
1. **Resolve scope** — apply the scope reference above and save the concrete file list to `.mz/task/<task_name>/scope_files.txt`. Skip excluded markdown directories unless explicitly requested.
1. **Task name** — `<YYYY_MM_DD>_clean_leftovers_<slug>` where `<slug>` is snake_case of scope mode + first 3 words of any path filter (max 20 chars). On same-day collision append `_v2`, `_v3`.
1. **Create task dir & state** — `.mz/task/<task_name>/`. Write `state.md` per [`skills/shared/state-schema.md`](../shared/state-schema.md): first line `schema_version: 2`, required keys (`Status`, `Phase`, `Started`, `Iteration` 0, `FilesWritten`, `phase_complete: false`, `what_remains: []`), plus skill-specific (`scope`, `files_in_scope`, `categories_to_clean`).
1. **Emit a visible setup block** — task name, scope, file count, exclusions. Read `phases/research.md` and proceed to Phase 1.

### Phase 2.5: Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

See [`skills/shared/approval-gate.md`](../shared/approval-gate.md) for the two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format.

**Mandatory pre-read**: Read `.mz/task/<task_name>/detection.md` with the Read tool. Capture the full file contents (per-category hit lists with file:line citations, severity classification, and the proposed cleanup plan) into context.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `detection.md`. Do not substitute a path, summary, or `<placeholder>` token.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Detection ready for review**
Found <N> artifact hits across <M> files in <K> categories. The cleanup plan auto-deletes AI signatures, phase markers, and planning comments; WHAT-not-WHY comments and dead-code blocks are reviewed per-instance.

- **Approve** → proceed to Phase 3 (cleanup) using the proposed plan
- **Reject** → mark task aborted, no files edited
- **Feedback** → adjust the plan per your input, re-run detection if needed, loop back here

Approve cost (estimated): <N> agents × ~20k tokens ≈ ~$<Y.YY> on Opus
```

Compute `<N>` as `ceil(<files_in_scope> / MAX_FILES_PER_DISPATCH)` plus the verification re-scan, capped at `MAX_PARALLEL_AGENTS × MAX_FIX_ITERATIONS`. Use `shared/approval-gate.md` to convert to a dollar estimate.

Invoke AskUserQuestion with this body (where `<verbatim detection.md contents>` is replaced by the bytes just read):

```
Detection complete. Please review and approve the cleanup plan:

<verbatim detection.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → update state to `detection_approved`, proceed to Phase 3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust the plan, overwrite `detection.md`, return to this gate, re-read it, re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** → skip the AskUserQuestion call, log `auto-approved (unattended mode)`, and proceed. The pre-gate block is still emitted.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above. Reference: grep `references/artifact-catalog.md` for category-specific patterns; do not load the entire file.

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

## Error Handling

- Empty scope → report and exit cleanly; do not dispatch agents.
- Research dispatch fails twice → continue with embedded catalog and flag in the report.
- Cleaner `BLOCKED` → preserve file unmodified, escalate via AskUserQuestion. Cleaner `NEEDS_CONTEXT` → fill missing context, re-dispatch.
- Linter not detected → record `n/a` and continue; do not silently skip. Update `state.md` before and after every agent dispatch.

## State Management

After each phase update `state.md`: `Status`, `Phase`, `Iteration` (cleanup loop), `FilesWritten` (cumulative), `categories_remaining` (categories with residuals after latest verification scan). Never rely on conversation memory for cross-phase state.

Maintain the progress ledger on every phase transition: set `phase_complete: false` on entering a phase and `true` only once its artifacts are written and its gates pass; refresh `what_remains` (outstanding work as plain strings) — it MUST be `[]` when `Status: complete`. Stamp `last_verified` whenever a verification gate passes clean. Reading a `schema_version: 1` or unversioned `state.md` upgrades it in place: add the ledger keys, set `schema_version: 2`, and log the upgrade.
