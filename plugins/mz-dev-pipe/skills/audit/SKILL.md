---
name: audit
description: ALWAYS invoke when the user wants to audit, find bugs, or review the codebase for issues. Triggers - audit, find bugs, security review, code quality scan. Produces a report-only findings file and does not modify code. When NOT to use - single-file fix (use debug), new feature (use build).
argument-hint: '[scope:branch|global|working] [optional focus — e.g. concurrency bugs, audit src/auth, security review]'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Autonomous Problem-Locator Pipeline (report-only)

## Overview

Orchestrates a multi-lens codebase audit and produces a ranked findings report. Parallel researchers scan across correctness, security, performance, maintainability, and reliability lenses. Findings are consolidated, ranked, and written to `findings.md` plus a human-readable `summary.md`. No code is modified. If the user wants the findings fixed, they can invoke `build`, `debug`, or `polish` against the summary.

## When to Use

- User asks to audit, find bugs, or review the codebase for issues.
- Triggers: "audit", "find bugs", "security review", "check for issues", "code quality scan".
- Scope spans multiple files / multiple concern categories.

### When NOT to use

- A single known bug — use `debug`.
- Building new functionality — use `build`.
- Map-reduce cleanup with no bug hunt — use `optimize`.
- Impact analysis only — use `blast-radius`.
- You want the findings fixed automatically — this skill does not edit code; pass the summary to `build`, `debug`, or `polish` afterwards.

## Input

- `$ARGUMENTS` — Optional lens hint (`"security review"`), scope hint (`"src/auth/"`), combined, or empty (roam mode — full repo minus vendored/generated/test). If ambiguous, ask. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- `scope:` controls files, remaining argument text controls lenses (orthogonal).
- **Default**: path-like tokens → scope, no path tokens → roam.
- `global` mode additionally excludes test files in this skill.

## Core Principles

1. **Research only.** This skill is read-only — it finds and reports, it does not fix.
1. **Parallel lenses, consolidated output.** Diverse lenses find different bug classes; one merged report is the final artifact.

## Constants

- **MAX_RESEARCHERS**: 5
- **CRITICAL_CAP**: unlimited | **HIGH_CAP**: 10 | **MEDIUM_CAP**: 5 | **LOW_CAP**: 0 (count only)
- **TASK_DIR**: `.mz/task/`

## Core Process

### Phase Overview

| #   | Phase                  | Reference                | Loop? |
| --- | ---------------------- | ------------------------ | ----- |
| 0   | Setup                  | inline below             | —     |
| 1   | Scope & Lens Selection | `phases/research.md`     | —     |
| 2   | Multi-Lens Research    | `phases/research.md`     | —     |
| 3   | Consolidate & Rank     | `phases/research.md`     | —     |
| 4   | Final Report           | `phases/final_report.md` | —     |

### Phase 0: Setup

Derive `<YYYY_MM_DD>_audit_<slug>`, create `.mz/task/<task_name>/`, write `state.md` (Status, Phase, Started, Review iterations). TaskCreate per phase.

### Phase 1–3: Research

- **Phase 1 — Scope & Lens**: parse (scope, lens). Pure path → all 5 lenses narrowed. Keywords → matching lenses on roam. Ambiguous → ask. See `phases/research.md` → Phase 1.
- **Phase 2 — Multi-Lens Research**: dispatch 1-5 `pipeline-researcher` (model: sonnet) in one message, one per lens. See `phases/research.md` → Phase 2.
- **Phase 3 — Consolidate & Rank**: merge, dedupe, rank by severity then confidence, apply caps. Zero findings ≥ medium → report clean, exit. See `phases/research.md` → Phase 3.

Note: ignore any references in `phases/research.md` to a later fix/approval phase — this skill stops at the report.

### Phase 4: Final Report

See `phases/final_report.md`. Write `summary.md`, report to user, update state to `completed`. No approval gate — the report is the deliverable.

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
