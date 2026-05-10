---
name: audit
description: ALWAYS invoke when the user wants to audit, find bugs, or review the codebase for issues. Triggers - audit, find bugs, security review, code quality scan, pre-PR audit, ship audit. Produces a report-only findings file and does not modify code. Supports depth:standard (default, quick lens scan) and depth:deep (pre-PR multi-wave with rollback rehearsal + blinded adversarial lenses). When NOT to use - single-file fix (use debug), new feature (use build).
argument-hint: '[depth:standard|deep] [scope:branch|global|working] [optional focus]'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Problem-Locator Pipeline (report-only)

## Overview

Orchestrates a multi-lens codebase audit and produces a ranked findings report. Two depth modes:

- **`depth:standard`** (default) — single-wave parallel researchers across correctness, security, performance, maintainability, and reliability lenses. Quick scan suitable for in-progress work or focused bug hunts. Cap mode: `quick` per `shared/severity-lattice.md`.
- **`depth:deep`** — pre-PR multi-wave audit with blast-radius tier gating, evidence-tiered severity caps, trust-boundary STRIDE delta, three blinded adversarial lenses, rollback rehearsal (BLOCKING for missing down-migrations), cognitive-load budget, and persistent ledger append. Cap mode: `pre-PR`.

No code is modified in either mode. Hand the summary to `build`, `debug`, or `polish` to act on it.

## When to Use

- User asks to audit, find bugs, or review the codebase for issues.
- Triggers (standard): "audit", "find bugs", "security review", "check for issues", "code quality scan".
- Triggers (deep): "deep audit", "pre-PR audit", "ship audit", "audit before publishing", "before I open a PR".
- Scope spans multiple files / multiple concern categories.

### When NOT to use

- A single known bug — use `debug`.
- Building new functionality — use `build`.
- Map-reduce cleanup with no bug hunt — use `optimize`.
- You want the findings fixed automatically — this skill does not edit code; pass the summary to `build`, `debug`, or `polish` afterwards.

## Input

- `$ARGUMENTS` — Optional `depth:` modifier (default `standard`), scope hint (`scope:branch`), lens hint (`"security review"`), or combination. If ambiguous, ask. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- `scope:` controls files, remaining argument text controls lenses (orthogonal).
- **Default**: `depth:standard` → path-like tokens → scope, no path tokens → roam. `depth:deep` → default scope `branch`.
- `global` mode additionally excludes test files in this skill.
- Bounded scopes (`branch`, `working`, path-list) auto-invoke `shared/blast-radius.md` to expand the inspection set with downstream-impacted files. `global` skips the auto-invocation.

## Core Principles

1. **Research only.** This skill is read-only — it finds and reports, it does not fix.
1. **Parallel lenses, consolidated output.** Diverse lenses find different bug classes; one merged report is the final artifact.
1. **Severity lattice is shared.** Both depth modes produce findings on the same 6-level lattice (`shared/severity-lattice.md`) so reports compare cleanly.

## Constants

- **MAX_RESEARCHERS**: 5 (standard) | **MAX_RESEARCHERS_WAVE_A**: 6 (deep) | **MAX_RESEARCHERS_WAVE_B**: 3 (deep)
- **Severity caps**: resolved per `shared/severity-lattice.md` — `quick` mode for standard, `pre-PR` mode for deep.
- **TASK_DIR**: `.mz/task/` | **LEDGER_PATH**: `.mz/reports/audit_ledger.md` (deep mode only)
- **HOTSPOT_LOOKBACK_DAYS**: 90 (deep mode only — git log lookback for hotspot table; falls back to all-history on shallow clones)

## Core Process

### Phase Overview

#### `depth:standard` (default)

| #   | Phase                  | Reference                | Loop? |
| --- | ---------------------- | ------------------------ | ----- |
| 0   | Setup                  | inline below             | —     |
| 1   | Scope & Lens Selection | `phases/research.md`     | —     |
| 2   | Multi-Lens Research    | `phases/research.md`     | —     |
| 3   | Consolidate & Rank     | `phases/research.md`     | —     |
| 4   | Final Report           | `phases/final_report.md` | —     |

#### `depth:deep`

| #   | Phase                                               | Reference                       | Loop? |
| --- | --------------------------------------------------- | ------------------------------- | ----- |
| 0   | Setup (+ tooling detect + git hotspots)             | inline below                    | —     |
| 1   | Scope Intelligence Gate (T0–T3 tiering)             | `phases/scope_and_tier_deep.md` | —     |
| 2   | Multi-Lens Research (Wave A + Wave B)               | `phases/research_deep.md`       | —     |
| 3   | Consolidate, Evidence-Cap, Rollback, Cognitive-Load | `phases/consolidate_deep.md`    | —     |
| 4   | Final Report + Ledger Update                        | `phases/final_report_deep.md`   | —     |

### Phase 0: Setup

Derive `<YYYY_MM_DD>_audit_<slug>` (or `<YYYY_MM_DD>_deep_audit_<slug>` when `depth:deep`). Apply the resume-check contract in [`skills/shared/resume-protocol.md`](../shared/resume-protocol.md): if `.mz/task/<task_name>/state.md` exists with `Status: running | failed`, present the Resume gate and re-enter per recorded `Phase`. Otherwise create `.mz/task/<task_name>/` and write `state.md` per [`skills/shared/state-schema.md`](../shared/state-schema.md) — first line MUST be `schema_version: 1`, followed by `Status`, `Phase`, `Started`, `Iteration` (review iterations), `FilesWritten`, plus skill-specific keys (`depth: standard|deep`). TaskCreate per phase.

When `depth:deep`: additionally dispatch `pipeline-tooling-detector` to detect test/lint commands for informational purposes (no tests are run); write to `.mz/task/<task_name>/tooling.md`. Phase 1 also computes git hotspot scores (commit counts over the last `HOTSPOT_LOOKBACK_DAYS` days, bot commits filtered) and records them in `scope.md`.

### Phases 1–4

Route by `depth:` to the phase files in the table above. Both depth modes stop at the report — neither modifies code. The blinded invariant in `depth:deep` Phase 2 (Wave B dispatched in a SEPARATE message after Wave A completes) is non-negotiable.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above. Reference files: grep `references/owasp-top-10-checklist.md` for specific OWASP categories — do not load the entire file.

## Common Rationalizations

| Rationalization                       | Rebuttal                                                               |
| ------------------------------------- | ---------------------------------------------------------------------- |
| "severity is subjective, label later" | "unlabeled audits get ignored"                                         |
| "one-pass scan is enough"             | "multi-lens is the point of an audit; single-lens is a grep"           |
| "let me just fix this one thing"      | "audit is report-only; fixing mid-run destroys the report's integrity" |

## Red Flags

- You modified code. This skill does not edit files; if fixes are needed, hand off to `build`, `debug`, or `polish`.
- Findings were not severity-labeled before writing `summary.md`.
- A single-lens scan was declared "audit complete".

## Verification

Output the final `summary.md` block: finding counts by severity, files touched (scanned, not modified), lenses run, path to `findings.md` for the full detail.

## Error Handling

- **Ambiguous argument**: ask before Phase 1. **Empty scope / zero findings**: report and exit.
- **Researcher fails**: continue with remaining lenses, flag in the report.
- **Write conflict on findings.md**: retry once, then escalate.

## State Management

Update `state.md` after each phase with current phase, files scanned, escalation notes. Allows resumption if interrupted.
