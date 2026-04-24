---
name: deep-audit
description: Report-only pre-PR audit pipeline with blast-radius tier gating, evidence-tiered severity caps, trust-boundary STRIDE delta, blinded adversarial lenses, rollback rehearsal, cognitive-load budget, and persistent findings ledger. Use before publishing a PR. Produces a report and does not modify code.
argument-hint: '[scope:branch|global|working]'
model: opus
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Pre-PR Deep Audit Pipeline (report-only)

## Overview

Orchestrates a deep pre-PR scan and produces a ranked findings report. Uses blast-radius tier gating (T0–T3), evidence-tiered severity caps, trust-boundary STRIDE delta analysis, three blinded adversarial lenses (production breakage, security adversary, ops/reliability), rollback rehearsal that flags missing rollback stories as BLOCKING, and a cognitive-load budget. Writes `findings.md`, `rollback_plan.md`, and `summary.md`. Appends BLOCKING findings to a persistent `findings_ledger.md` across audit runs. All researchers run on opus. Default scope is `scope:branch`. No code is modified — hand the report to `build`, `debug`, or `polish` to act on it.

## When to Use

- User wants a deep audit report before publishing a PR.
- Triggers: "deep audit", "pre-PR audit", "ship audit", "audit before publishing", "before I open a PR".
- Spans multiple files and benefits from multi-lens + adversarial analysis.

### When NOT to use

- Simple known bug — use `debug`.
- Quick code quality scan — use `audit` (also report-only, lighter weight).
- New feature — use `build`.
- You want findings fixed automatically — this skill does not edit code; pass the summary to `build`, `debug`, or `polish` afterwards.

## Input

- `$ARGUMENTS` — Optional `scope:` override (default: `scope:branch`).

## Constants

- **MAX_RESEARCHERS_WAVE_A**: 6 | **MAX_RESEARCHERS_WAVE_B**: 3
- **HIGH_CAP**: unlimited | **MEDIUM_CAP**: 10 | **LOW_CAP**: 0 (count only)
- **TASK_DIR**: `.mz/task/` | **LEDGER_PATH**: `.mz/audit/findings_ledger.md`
- **HOTSPOT_LOOKBACK_DAYS**: 90 *(git log lookback window for scope.md hotspot table; falls back to all-history on shallow clones)*

## Core Process

### Phase Overview

| #   | Phase                                               | Reference                  | Loop? |
| --- | --------------------------------------------------- | -------------------------- | ----- |
| 0   | Setup                                               | inline below               | —     |
| 1   | Scope Intelligence Gate                             | `phases/scope_and_tier.md` | —     |
| 2   | Multi-Lens Research (Wave A + Wave B)               | `phases/research.md`       | —     |
| 3   | Consolidate, Evidence-Cap, Rollback, Cognitive-Load | `phases/consolidate.md`    | —     |
| 4   | Final Report + Ledger Update                        | `phases/final_report.md`   | —     |

### Phase 0: Setup

Derive `deep-audit_<slug>_<HHMMSS>`, create `.mz/task/<task_name>/`, write `state.md` (Status, Phase, Started). TaskCreate per phase. Dispatch `pipeline-tooling-detector` to detect test/lint commands for informational purposes only (no tests are run); write to `.mz/task/<task_name>/tooling.md`. Phase 1 additionally computes git hotspot scores (commit counts over the last `HOTSPOT_LOOKBACK_DAYS` days, bot commits filtered) and records them in `scope.md` so Wave A researchers can prioritise high-churn files.

### Phases 1–3: Research and Consolidation

- **Phase 1** — See `phases/scope_and_tier.md`. Parse scope argument (default `scope:branch`), materialise file list, classify T0–T3, identify trust boundary delta at T2+, write `scope.md`.
- **Phase 2** — See `phases/research.md`. Wave A = 6 opus researchers (5 standard lenses + STRIDE-delta). Wave B = 3 opus blinded adversarial researchers dispatched AFTER Wave A in a separate message. Writes per-lens findings artifacts.
- **Phase 3** — See `phases/consolidate.md`. Merge, dedupe, blinded cross-reference, evidence-tier cap, rollback rehearsal (BLOCKING findings for missing down-migrations/migration plans), cognitive-load score (SPLIT RECOMMENDATION if >40). Writes `findings.md` and `rollback_plan.md`.

Note: ignore any references in the phase files to a later fix/approval phase — this skill stops at the report. Blinded invariant still applies: Wave B must be dispatched in a separate message AFTER Wave A completes.

### Phase 4: Final Report + Ledger Update

See `phases/final_report.md`. Write `summary.md`, append BLOCKING findings to `.mz/audit/findings_ledger.md` (append-only), report to user, update state to `completed`. No approval gate — the report is the deliverable.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above. Reference files: read `references/` files on demand, do not load entire files — grep for specific terms.

## Common Rationalizations

| Rationalization                                        | Rebuttal                                                                                  |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| "let me just fix this one BLOCKING finding"            | "deep-audit is report-only; fixing mid-run destroys report integrity and ledger accuracy" |
| "blinded wave is redundant if Wave A found everything" | "Wave B breaks confirmation bias; corroboration is a feature, not redundancy"             |
| "rollback rehearsal is overhead for small PRs"         | "data-migrating and contract-breaking changes are silent until they fail in prod"         |

## Red Flags

- You modified code. This skill does not edit files; hand off to `build`, `debug`, or `polish`.
- Wave B dispatched in the same message as Wave A (blinded guarantee violated).
- BLOCKING findings not appended to the ledger.
- Ledger rows overwritten instead of appended.

## Verification

Output `summary.md` path, finding counts by severity, tier classification, Wave A + Wave B lens list, cognitive-load score, BLOCKING count, ledger append count, and confirmation that no files outside `.mz/` were modified.

## Error Handling

- Ambiguous argument → ask before Phase 1. Empty scope / zero findings → report and exit.
- Researcher fails → continue remaining lenses, flag in summary.
- `.mz/audit/` directory missing → create it before writing the ledger.
- Ledger write conflict → retry once, then escalate.

## State Management

Update `state.md` after each phase with current phase, wave counts, files scanned, escalation notes. Allows resumption if interrupted.
