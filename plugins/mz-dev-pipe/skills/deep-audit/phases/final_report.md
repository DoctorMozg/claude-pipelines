# Phase 4: Final Report + Ledger Update

**Goal**: Turn `findings.md` and `rollback_plan.md` into a human-readable `summary.md`, append BLOCKING findings to the persistent ledger, and report to the user. No approval gate — the report is the deliverable. No code is modified.

## 4.1 Write summary

Read `.mz/task/<task_name>/findings.md` and `.mz/task/<task_name>/rollback_plan.md`, then write `.mz/task/<task_name>/summary.md`:

```markdown
# Deep Audit Summary

**Argument**: <original argument or "scope:branch">
**Task directory**: .mz/task/<task_name>/
**Completed**: <timestamp>
**Mode**: report-only (no code was modified)

## Overview
- Scope: <branch / global / working>
- Blast-radius tier: T0 / T1 / T2 / T3
- Files scanned: N
- Lenses run (Wave A): correctness, security, performance, maintainability, reliability, stride_delta
- Lenses run (Wave B, blinded): blinded_production, blinded_security, blinded_ops
- Total findings located (before caps): <raw count>
- Findings in report (after caps): <count>
- BLOCKING findings (rollback analysis): R
- Cognitive-load score: S [SPLIT RECOMMENDED if >40]
- Skeptic pass: <challenged> challenged, <downgraded> downgraded, <verified> verified, <fix_unclear> FIX_UNCLEAR

## BLOCKING Findings
#### ROLLBACK-<n> — <file:line>
- Severity: critical
- Evidence tier: T2
- Description: <one line>

## Findings
### Critical / High (top 10) / Medium (top 10)
#### F<id> — <file:line>
- Lens: <lens>
- Confidence: <level>
- Evidence tier: T0 / T1 / T2 / T3
- Severity original / capped: <pair>
- Description: <one line>
- Proposed fix: <one line from findings.md>

## Blind Spots (Wave B — unmatched by Wave A)
#### BS<id> — <file:line or "location unknown">
- Source: blinded_<production|security|ops>
- Evidence tier: T2 / T3
- Description: <one line>

## Rollback Plan (abbreviated)
<top rollback concerns — link to rollback_plan.md for full detail>

## Split Recommendation (if score > 40)
<cut-point suggestions from findings.md>

## Deferred (below cap)
- <count> high below the cap
- <count> medium below the cap
- <count> low/advisory findings

## Next Steps
- To have these findings fixed, pass this summary to `build`, `debug`, or `polish`.
- BLOCKING findings should be resolved before opening a PR.
```

## 4.2 Update findings ledger

Read `LEDGER_PATH` (`.mz/audit/findings_ledger.md`). If the file does not exist, create it (along with `.mz/audit/` directory) with this header:

```markdown
# Deep Audit Findings Ledger

Tracks BLOCKING findings across audit runs. Each row is a single finding.

| finding_id | file_line | severity | evidence_tier | status | first_seen | needs_resolution_by |
| ---------- | --------- | -------- | ------------- | ------ | ---------- | ------------------- |
```

For each **BLOCKING finding** (findings with ID `ROLLBACK-N` or findings with `BLOCKING` in their description from rollback rehearsal) produced by this run: append one row with `status=open`, `first_seen=<today>`, `needs_resolution_by=<today + 14 days>`.

Do NOT modify existing rows in the ledger. Append-only. Deduplication across runs (same `file_line` + same finding semantics) is out of scope for this skill — users can manually close rows when resolved in follow-up work.

## 4.3 Report to user

Display:

- Paths to `summary.md`, `findings.md`, `rollback_plan.md`, and `LEDGER_PATH`
- Headline: "Found X findings (N critical, M high, P medium, R BLOCKING) across K files at tier T<n>. Report-only — no code was modified."
- Cognitive-load score + SPLIT RECOMMENDATION if emitted
- Blind-spot count (Wave B findings unmatched by Wave A)
- Ledger append count: "<n> BLOCKING findings appended to .mz/audit/findings_ledger.md"
- Suggest `/build`, `/debug`, or `/polish` for the user to follow up on specific findings.

Update state file status to `completed`.
