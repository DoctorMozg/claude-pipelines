# Phase 4: Verification + Report

The orchestrator re-scans the edited files, runs the project linter/formatter, produces the final report, and either declares the task complete or loops back to Phase 3 with the residual list.

## 4.1 Re-scan

Re-run the Phase 2 detection scan on the same `scope_files.txt`. Use the same catalog patterns; do not require fresh research. Output: `.mz/task/<task_name>/verification_scan.md` with the same structure as `detection.md` but reflecting post-cleanup state.

Diff against the original `detection.md`:

- **Removed** — hits that were in `detection.md` and are no longer in `verification_scan.md`. These count toward per-category "Artifacts removed" in the final report.
- **Residual** — hits still present (the cleaner missed them, judged them WHY, or marked them BLOCKED).
- **New** — hits in `verification_scan.md` not in `detection.md`. These should not exist; flag as a `## Concerns` block in the report and force escalation.

Write the diff to `.mz/task/<task_name>/residuals.md`.

## 4.2 Run the linter

Detect the project's linter via `Bash`:

1. **Python** — check for `ruff` (preferred), `flake8`, `pylint` in order. Run on edited files only: `ruff check <files>` or equivalent.
2. **JavaScript / TypeScript** — check for `eslint`, `biome`, `oxlint`. Run on edited files only.
3. **Go** — `go vet ./...` plus `golangci-lint run` if available.
4. **Rust** — `cargo clippy --no-deps`.
5. **Other** — look for `Makefile` targets `lint`, `check`, `format`, or scripts under `scripts/lint*`.

If no linter is detected, record `linter: n/a` in the final report. Do not silently skip; the report shows the linter was attempted.

Record results to `.mz/task/<task_name>/lint_results.md` with: linter name, files checked, failures, fixable vs non-fixable counts.

The linter pass surfaces unused-import dead code (category E item) that the cleaner agent did NOT touch. If unused-import findings exist, the orchestrator may dispatch one final cleanup wave scoped specifically to those findings.

## 4.3 Decide: complete, loop, or escalate

Three outcomes:

### Complete

- `residuals.md` is empty (or contains only category-D items the cleaner deliberately kept with `decision: keep`).
- Linter pass returns clean (or `n/a`).
- → Update `state.md` to `Status: complete`, `Phase: 4`. Write the final report (step 4.4). Emit the verification block (step 4.5).

### Loop back to Phase 3

- `residuals.md` is non-empty AND `Iteration < MAX_FIX_ITERATIONS`.
- → Increment `Iteration` in `state.md`. Read `phases/cleanup.md` (re-entry rules in §3.5). Dispatch a residual-focused wave.

### Escalate

- `residuals.md` is non-empty AND `Iteration >= MAX_FIX_ITERATIONS`.
- → Present the residuals to the user via AskUserQuestion. Pre-gate emit block:

  ```
  **Cleanup hit iteration cap**
  Reached MAX_FIX_ITERATIONS (3) with residuals remaining. The listed hits resisted automatic cleanup — they may need manual review.

  - **Accept** → mark task complete with documented residuals in the report
  - **Force one more pass** → bypass the cap once and run one more cleanup wave
  - **Abort** → mark task failed; report records the residuals as outstanding
  ```

  AskUserQuestion body contains the verbatim `residuals.md` contents and closes with `Type **Accept** to accept residuals, **Force** to run one more pass, **Abort** to stop, or type your feedback.`. This is a variant gate; the bypass options `Force` and `Abort` are mutually exclusive with `Accept`.

## 4.4 Write the final report

Path: `.mz/reports/<YYYY_MM_DD>_clean_leftovers_<slug>.md`. On same-day collision append `_v2`, `_v3`.

Structure:

```markdown
# Leftover Cleanup Report — <task_name>

## Summary
- Scope: <working|branch|global>
- Files in scope: <N>
- Files edited: <N>
- Iterations: <N>
- Final status: <complete|complete_with_residuals|failed>

## Artifacts removed (by category)
| Category | Original hits | Removed | Residual |
|----------|---------------|---------|----------|
| A — AI signatures           | <N> | <N> | <N> |
| B — Phase markers           | <N> | <N> | <N> |
| C — Planning comments       | <N> | <N> | <N> |
| D — WHAT-not-WHY (flagged)  | <N> | <N> (deleted) / <N> (kept as WHY) | <N> |
| E — Dead code               | <N> | <N> | <N> |

## Linter
- Detected: <ruff|eslint|...|none>
- Files checked: <N>
- Result: <pass|fail|n/a>
- Failures: <list, or none>

## Residuals (if any)
<verbatim contents of residuals.md, or "None.">

## Concerns (if any)
- <Any new hits introduced by cleanup — should be empty>
- <Any BLOCKED cleaner returns>

## Files edited
<list of paths>

## Research provenance
- Status: <complete|unavailable>
- Source path: .mz/task/<task_name>/web_research.md
```

## 4.5 Emit the verification block

Print to chat (the final user-facing surface):

```
Cleanup complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_clean_leftovers_<slug>.md
Scope:      <working|branch|global> (<N> files in scope)
Artifacts removed (by category):
  AI signatures:        <N>
  Phase markers:        <N>
  Planning comments:    <N>
  WHAT-not-WHY comments:<N> (of <M> flagged)
  Dead code blocks:     <N>
Iterations:  <N>
Linter:      <pass|fail|n/a>
Residuals:   <none|N hits — see report>
```

If `Final status: failed`, replace the first line with `Cleanup incomplete — see report for residuals.` and surface the residual count prominently.

## 4.6 Final state update

Update `state.md`:

- `Status: complete | complete_with_residuals | failed`
- `Phase: 4`
- Append `verification_scan.md`, `residuals.md`, `lint_results.md`, and the final report path to `FilesWritten`.

Phase 4 is the terminal phase. Do not re-enter once `Status: complete`.
