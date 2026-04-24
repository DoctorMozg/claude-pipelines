# Phase 4: Final Report

**Goal**: Turn `findings.md` into a human-readable `summary.md` and report to the user. No approval gate — the report is the deliverable. No code is modified.

## 4.1 Write summary

Read `.mz/task/<task_name>/findings.md` and write `.mz/task/<task_name>/summary.md`:

```markdown
# Audit Summary

**Argument**: <original argument or "roam">
**Task directory**: .mz/task/<task_name>/
**Completed**: <timestamp>
**Mode**: report-only (no code was modified)

## Overview
- Scope: <roam / narrowed>
- Files scanned: N
- Lenses run: <list>
- Total findings located (before caps): <raw count>
- Findings in report (after caps): <count>
- Findings skipped by caps: <breakdown by severity>

## Findings
### Critical
#### F<id> — <file:line>
- Lens: <lens>
- Confidence: <level>
- Description: <one line>
- Proposed fix: <one line from findings.md>

### High (top 10 of <total>) / Medium (top 5 of <total>)
(same format as Critical above)

## Deferred (below cap)
- <count> high below the cap
- <count> medium below the cap
- <count> low/advisory findings

## Next Steps
- To have these findings fixed, pass this summary to `build`, `debug`, or `polish`.
- For a deeper pre-PR audit with blast-radius tiering and blinded adversarial lenses, use `deep-audit`.
```

## 4.2 Report to user

Display:

- Path to `summary.md` and `findings.md`
- Headline: "Found X findings (N critical, M high, P medium) across K files. Report-only — no code was modified."
- Deferred counts (below-cap + low severity)
- Suggest `/build`, `/debug`, or `/polish` for the user to follow up on specific findings.

Update state file status to `completed`.
