# Phase 3: Consolidate, Evidence-Cap, Rollback, Cognitive-Load

**Goal**: Turn per-lens findings (Wave A + Wave B) into one evidence-capped, rollback-analyzed, cognitive-load-budgeted report. Write `findings.md` and `rollback_plan.md`.

## 3.1 Merge and Dedupe

Read all `findings_<lens>.md` files (Wave A: correctness, security, performance, maintainability, reliability, stride_delta; Wave B: blinded_production, blinded_security, blinded_ops).

Dedupe findings that point to the same `file:line` from multiple lenses:

- **Same file:line, same category** → keep one, note that multiple lenses flagged it (raises confidence by one level)
- **Same file:line, different categories** → keep both; they are different issues co-located
- **Overlapping ranges** (lens A flags lines 42-50, lens B flags lines 45-48) → keep both but link them

Assign each unique finding a stable numeric ID (`F1`, `F2`, ...).

## 3.2 Blinded Cross-Reference

For each Wave B finding (blinded_production, blinded_security, blinded_ops):

1. Check if it maps to an existing finding from Wave A (same file:line or same described behavior)
1. If a match exists → merge (note the blind-spot corroboration, treat as confidence boost)
1. If NO match exists → this is a **blind spot** — a gap that context-aware analysis missed

All unmatched Wave B findings are promoted to a dedicated "Blind Spots" section in `findings.md`. They receive a minimum evidence tier of T2 if they cite a specific file:line, T3 otherwise. They are NOT given severity ranks by Wave B researchers — the consolidation agent assigns severity based on the description, at the evidence-tier-capped maximum.

## 3.3 Evidence-Tiered Severity Cap

Read `references/evidence-tier-rules.md` for the full tier definitions and capping rules.

For each finding, read its `evidence_tier` field:

- If the researcher did not provide `evidence_tier`, assign T3 (Advisory) by default
- Compare the asserted severity against the evidence-tier maximum (T0→Critical, T1→High, T2→Medium, T3→Low)
- If asserted severity > tier maximum → **cap** the finding:
  - Set `severity_capped` to the tier maximum
  - Preserve `severity_original` and `evidence_tier` in the finding record
  - Add `cap_reason`: one sentence explaining the mismatch

After capping, apply per-tier limits (read from SKILL.md constants):

- Critical: include ALL (HIGH_CAP = unlimited)
- High: top `MEDIUM_CAP = 10` by confidence
- Medium: top 10 by confidence
- Low / Advisory: record count, skip from report

Within each severity tier, sort by confidence (high > medium > low), breaking ties by lens priority: correctness > security > reliability > stride_delta > performance > maintainability.

Findings below the cap are NOT discarded — they go to a "Deferred" section.

## 3.4 Rollback Rehearsal

Read the `Reversibility Map` from `.mz/task/<task_name>/scope.md`.

For each changed file, apply these rules:

| Reversibility class | Rule                                                                                                                                                                                           |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `reversible`        | No action needed — `git revert` is sufficient                                                                                                                                                  |
| `forward-only`      | Emit advisory note in `rollback_plan.md`: manual steps may be needed to revert                                                                                                                 |
| `data-migrating`    | Search for a corresponding down-migration file. If not found → emit **BLOCKING finding** (severity: critical, confidence: high, evidence_tier: T2). The blocking finding ID is `ROLLBACK-<n>`. |
| `contract-breaking` | Search for a migration plan or deprecation notice. If not found → emit **BLOCKING finding** with same rules as above.                                                                          |

For `data-migrating` checks, search:

- Files named `*_down.py`, `*_rollback*`, `*reverse*` in the same migration directory
- The migration file itself for a `downgrade()` function (SQLAlchemy/Alembic pattern) or `down()` method (Flyway/Liquibase)

For `contract-breaking` checks, search:

- `MIGRATION.md`, `BREAKING_CHANGES.md`, or changelog entries
- Protobuf files for field-number preservation (removal of a field number without reservation is breaking)

BLOCKING findings from rollback analysis are prepended to the findings list and cannot be capped or deferred — they are always in the report and are appended to the persistent ledger in Phase 4.

Write `.mz/task/<task_name>/rollback_plan.md`:

```markdown
# Rollback Plan

## Per-File Rollback Procedures

| File              | Class             | Rollback procedure                                                                       |
| ----------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| path/to/file.py   | reversible        | `git revert <commit>`                                                                    |
| db/migrations/0042.py | data-migrating | Run `alembic downgrade -1` (down-migration: [found/NOT FOUND])                           |
| api/schema.proto  | contract-breaking | Restore field numbers; notify downstream consumers (plan: [found/NOT FOUND])             |

## Blocking Findings from Rollback Analysis
- ROLLBACK-1: <description of missing down-migration or migration plan>

## Advisory Notes
- <file>: forward-only change — manual rollback steps: <description>
```

## 3.5 Cognitive-Load Budget

Read `Cognitive-Load Metrics` from `.mz/task/<task_name>/scope.md`.

Compute:

```
score = (file_count × 3) + (diff_LOC / 50) + (distinct_concern_count × 5)
```

If `score > 40`:

- Emit a **SPLIT RECOMMENDATION** section in `findings.md`
- Suggest 2-3 concrete cut points: which files or concerns could be split into a separate PR
- Example: "Split database migration (0042.py) into its own PR; the migration + application code change is a common high-risk combination"

For each finding in the report, estimate `reviewer_minutes_saved_if_fixed`:

- Cross-file refactors, complex logic bugs: 5–15 min
- Missing error handling, dead code: 2–5 min
- Naming issues, minor maintainability: 1–2 min

This estimate helps reviewers prioritize which findings to request fixes for most urgently.

## 3.6 Write findings.md

Write `.mz/task/<task_name>/findings.md`:

```markdown
# Consolidated Findings

## Summary
- Total findings: N (merged from <X> per-lens raw findings)
- Blind spots (Wave B unmatched): M
- Severity breakdown (after capping): critical=A, high=B (of B_total), medium=C (of C_total), low=D (advisory, skipped)
- BLOCKING findings (rollback analysis): R
- Cognitive-load score: S [SPLIT RECOMMENDED if >40]
- Lenses run: correctness, security, performance, maintainability, reliability, stride_delta, blinded_production, blinded_security, blinded_ops
- Files with findings: K (of N scanned)

## BLOCKING Findings (always in report, cannot be deferred)

### ROLLBACK-1 — <file:line>
- **Severity**: critical
- **Evidence tier**: T2
- **Description**: <missing down-migration or migration plan>
- **Proposed fix**: <create down-migration or add migration plan>
- **Reviewer minutes saved**: 10

## Plan (approved findings will be fixed)

### Critical
#### F1 — <file:line> — <lens> — confidence: <level>
- **Severity original**: critical
- **Severity capped**: critical
- **Evidence tier**: T0
- **Cap reason**: (none — evidence supports severity)
- **Description**: <one paragraph>
- **Proposed fix**: <one paragraph>
- **Reviewer minutes saved**: <estimate>

### High (top 10 of <total>)
#### F<id> — ...
- **Severity original**: <original>
- **Severity capped**: high
- **Evidence tier**: T1
- **Cap reason**: <if capped>
...

### Medium (top 10 of <total>)
...

## Blind Spots (Wave B — unmatched by Wave A lenses)

### BS1 — <file:line or "location unknown"> — blinded_<source>
- **Evidence tier**: T2 / T3
- **Description**: <what the blinded researcher found>
- **Severity assigned**: <based on evidence tier cap>

## Deferred (not in report)
- N additional high findings not included (below cap)
- M additional medium findings not included (below cap)
- K low/advisory findings skipped entirely

## Split Recommendation (if score > 40)
<concrete cut-point suggestions>
```

Update state file phase to `findings_consolidated`.

After writing, run `pre-commit run --files plugins/mz-dev-pipe/skills/deep-audit/phases/consolidate.md` and fix any issues before reporting STATUS: DONE.
