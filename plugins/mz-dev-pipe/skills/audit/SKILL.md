---
name: audit
description: ALWAYS invoke when the user wants to audit, find bugs, or review the codebase for issues. Triggers: "audit", "find bugs", "security review", "code quality scan". When NOT to use: single-file fix (use debug), new feature (use build).
argument-hint: [scope:branch|global|working] [optional focus — e.g. "concurrency bugs", "audit src/auth", "security review"]
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Problem-Locator Pipeline

## Overview

Orchestrates a multi-lens codebase audit. Parallel researchers scan across correctness, security, performance, maintainability, and reliability lenses. Findings are consolidated, ranked, approved by the user, then fixed in parallel with mirrored reviewers. Critical/high fixes get regression tests.

## When to Use

- User asks to audit, find bugs, or review the codebase for issues.
- Triggers: "audit", "find bugs", "security review", "check for issues", "code quality scan".
- Scope spans multiple files / multiple concern categories.

### When NOT to use

- A single known bug — use `debug`.
- Building new functionality — use `build`.
- Map-reduce cleanup with no bug hunt — use `optimize`.
- Impact analysis only — use `blast-radius`.

## Input

- `$ARGUMENTS` — Optional lens hint (`"security review"`), scope hint (`"src/auth/"`), combined, or empty (roam mode — full repo minus vendored/generated/test). If ambiguous, ask. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- `scope:` controls files, remaining argument text controls lenses (orthogonal).
- **Default**: path-like tokens → scope, no path tokens → roam.
- `global` mode additionally excludes test files in this skill.

## Core Principles

1. **Research first, fix later.** Do not touch code until findings are approved.
1. **Parallel where safe, sequential where necessary.** Ask when unclear.

## Constants

- **MAX_RESEARCHERS**: 5 | **MAX_CODERS**: 6 | **MAX_REVIEWERS**: 6 | **MAX_REVIEW_ITERATIONS**: 3 | **MAX_FIX_ATTEMPTS**: 3
- **CRITICAL_CAP**: unlimited | **HIGH_CAP**: 10 | **MEDIUM_CAP**: 5 | **LOW_CAP**: 0 (count only) | **REGRESSION_TEST_SEVERITIES**: `[critical, high]` | **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

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

### Phase 0: Setup

Derive `<YYYY_MM_DD>_audit_<slug>`, create `.mz/task/<task_name>/`, write `state.md` (Status, Phase, Started, Review iterations, Fix attempts, Lenses, Findings). TaskCreate per phase.

### Phase 1–3: Research

- **Phase 1 — Scope & Lens**: parse (scope, lens). Pure path → all 5 lenses narrowed. Keywords → matching lenses on roam. Ambiguous → ask. See `phases/research.md` → Phase 1.
- **Phase 2 — Multi-Lens Research**: dispatch 1-5 `pipeline-researcher` (model: sonnet) in one message, one per lens. See `phases/research.md` → Phase 2.
- **Phase 3 — Consolidate & Rank**: merge, dedupe, rank by severity then confidence, apply caps. Zero findings ≥ medium → report clean, exit. See `phases/research.md` → Phase 3.

### Phase 3.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/findings.md` with the Read tool. Capture the full file contents (every ranked finding with file:line, severity, confidence, description, proposed fix, plus the coder assignment preview block) into context.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `findings.md`. Never substitute a path, status summary, line count, or `<findings list>` placeholder — the user must review the actual ranked findings in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Findings Ready for Review**
Completed multi-lens audit with N ranked findings. Severity distribution and coder assignments shown.

- **Approve** → proceed to Phase 4 (parallel fix dispatch)
- **Reject** → abort task, no files modified
- **Feedback** → adjust findings list or scope, re-present via AskUserQuestion
```

Invoke AskUserQuestion with this body (where `<verbatim findings.md contents>` is replaced by the bytes you just read):

```
Found <N> actionable findings. Please review:

<verbatim findings.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
(e.g. "drop finding 3", "rerun research with security lens only", "narrow scope to src/api/").
```

**Response handling**:

- **"approve"** → proceed to Phase 4.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** — *drop/adjust* → remove from `findings.md` and re-present (no re-research). *Scope/lens changes* → re-run Phase 1, overwrite `findings.md`, then re-present. *Unclear* → ask follow-up. After any change, re-read `findings.md` and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 4 without explicit approval.

### Phase 4–10: Fix, Review, Finalize

- **Phase 4 — Chunk Findings**: group by affected file, same file → same coder, wave ≤ `MAX_CODERS`. See `phases/fix_and_verify.md` → Phase 4.
- **Phase 5 — Parallel Fix**: dispatch up to 6 `pipeline-coder` (opus) per wave. See `phases/fix_and_verify.md` → Phase 5.
- **Phase 6 — Verify & Auto-Fix**: re-run tests/linters; restore green before Phase 7. See `phases/fix_and_verify.md` → Phase 6.
- **Phase 7 — Parallel Review**: dispatch `pipeline-code-reviewer` (opus), 1:1 per chunk. See `phases/review_and_finalize.md` → Phase 7.
- **Phase 8 — Handle Verdicts**: re-dispatch rejected chunks; approved chunks frozen. See `phases/review_and_finalize.md` → Phase 8.
- **Phase 9 — Regression Tests**: for critical/high findings, dispatch `pipeline-test-writer`. See `phases/review_and_finalize.md` → Phase 9.
- **Phase 10 — Final Summary**: write `summary.md` with findings, fixes, tests, iterations, follow-ups. See `phases/review_and_finalize.md` → Phase 10.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.
Reference files: grep `references/owasp-top-10-checklist.md` for specific OWASP categories — do not load the entire file.

## Common Rationalizations

| Rationalization                        | Rebuttal                                                            |
| -------------------------------------- | ------------------------------------------------------------------- |
| "findings look obvious, skip approval" | "parallel fix dispatch is expensive; user approval is the cost cap" |
| "severity is subjective, label later"  | "unlabeled audits get ignored"                                      |
| "one-pass scan is enough"              | "multi-lens is the point of an audit; single-lens is a grep"        |

## Red Flags

- Findings were not severity-labeled before the approval gate.
- You dispatched fixes without explicit user approval of the findings list.
- A single-lens scan was declared "audit complete".

## Verification

Output the final `summary.md` block: finding counts by severity, fixed vs deferred, files touched, review iterations, and regression test list.

## Error Handling

- **Ambiguous argument**: ask before Phase 1. **Empty scope / zero findings**: report and exit.
- **No test framework**: ask user for command. **No linter**: note and skip.
- **Researcher fails**: continue with remaining lenses, flag in Phase 3.5.
- **Write conflict**: sequentialize next iteration. **Regression test fails**: escalate to user.

## State Management

Update `state.md` after each phase with current phase, iteration counts, files modified, escalation notes. Allows resumption if interrupted.
