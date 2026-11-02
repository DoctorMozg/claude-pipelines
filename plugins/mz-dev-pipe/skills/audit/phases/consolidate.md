# Phase 3: Consolidate & Rank

**Goal**: Turn per-lens finding files into one ranked, capped plan.

## 3.1 Merge and dedupe

Read all `findings_<lens>.md` files. Dedupe findings that point to the same `file:line` from multiple lenses:

- **Same file:line, same category** → keep one, note that both lenses flagged it (higher confidence)
- **Same file:line, different categories** → keep both; they're different issues coincidentally co-located
- **Overlapping ranges** (e.g., lens A flags lines 42-50, lens B flags lines 45-48) → keep both but link them

Assign each unique finding a stable numeric ID (`F1`, `F2`, ...).

## 3.2 Rank and apply caps

Within each severity tier, sort by confidence (high > medium > low), breaking ties by lens priority (correctness > security > reliability > performance > maintainability).

Apply the per-tier caps from the SKILL.md constants:

- **Critical**: include all (`CRITICAL_CAP`, no cap)
- **High**: top `HIGH_CAP`
- **Medium**: top `MEDIUM_CAP`
- **Low**: `LOW_CAP`, so none in the report body (record the count)

Findings over a cap are not dropped. Write them to `<PROJECT_ROOT>/.mz/task/<task_name>/findings_capped.md`, next to `findings.md`, in rank order and in the same finding format. Skip the file when nothing is over a cap. The report's "Deferred" section gives the counts and names the appendix, and the user is told "N additional <severity> findings not in the report body, listed in findings_capped.md".

## 3.3 Write findings artifact

Write `<PROJECT_ROOT>/.mz/task/<task_name>/findings.md`:

```markdown
# Consolidated Findings

## Summary
- Total findings: N (merged from <X> per-lens raw findings)
- Severity breakdown: critical=A, high=B (of B_total), medium=C (of C_total), low=D (skipped)
- Lenses run: <list>
- Files with findings: M (of K scanned)

## Plan (approved findings will be fixed)

### Critical
#### F1 — <file:line> — <lens> — confidence: <level>
- **Description**: <one paragraph>
- **Proposed fix**: <one paragraph>
- **Affected file**: <file>

#### F2 — ...

### High (top 10 of <total>)
#### F<id> — ...

### Medium (top 5 of <total>)
#### F<id> — ...

## Deferred (listed in findings_capped.md)
- N additional high findings (below top 10)
- M additional medium findings (below top 5)
- K low findings

## Files with findings
- `path/to/file_a.py`: F1, F4, F7 — 3 findings
- `path/to/file_b.py`: F2 — 1 finding
- `path/to/file_c.py`: F3, F5 — 2 findings
...

Total files with findings: K of N scanned
```

Update state file phase to `findings_ranked` and record total findings + files-with-findings count.

**If the plan has zero findings at severity ≥ medium**: before exiting cleanly, perform a file-count sanity check to distinguish a genuinely clean codebase from a scope resolution error (e.g., `.gitignore` over-exclusion that produced an empty file list).

1. Read `<PROJECT_ROOT>/.mz/task/<task_name>/scope.md` and extract the scanned file count (the `Total files: N` line under `## Scope`).

1. If the scanned file count is **0**, do NOT exit cleanly. Instead:

   - Emit `ZERO RESULTS UNVERIFIED` to the user.
   - Present this message: "All researchers returned zero findings, but the scoped file list was empty. This may indicate a scope resolution error (e.g., .gitignore over-exclusion). Please verify the scope and re-run, or confirm you intended to audit an empty file set."
   - Ask via AskUserQuestion whether to (a) re-run with corrected scope, or (b) confirm scope was correct and accept the clean result.

1. If the scanned file count is **> 0**, proceed with the normal zero-findings clean-exit message. Report to the user and exit cleanly — nothing to fix.
