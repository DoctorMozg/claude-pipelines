# Phase 4 — Apply Approved Edits

Reads `edits.json` and applies every edit via the `Edit` tool. Records successes, failures, and writes the final `summary.md`. Never commits.

## Contents

- [4.1 Load edits.json](#41-load-editsjson)
- [4.2 Apply edits](#42-apply-edits)
- [4.3 Handle apply failures](#43-handle-apply-failures)
- [4.4 Write summary.md](#44-write-summarymd)

______________________________________________________________________

## 4.1 Load `edits.json`

Read `.mz/task/<task_name>/edits.json`. Validate the structure:

- Top-level `files` list exists.
- Every file entry has an absolute `path` and a non-empty `edits` list. Empty `edits` lists indicate a Phase 3 bug — record in `apply_failures.md` and skip that file.
- Every edit has `id`, `old_string`, `new_string`, and `rationale`.

If any file's `path` is outside the repository root, refuse to apply that file's edits. Record in `apply_failures.md` with reason `path_outside_repo`. This guards against a proposer returning a poisoned path.

## 4.2 Apply edits

For each file in `files`:

1. `Read` the file first. Required before any `Edit` call — this both primes the harness and lets the orchestrator confirm the file still exists.
1. For each edit in the file's `edits` list, in order:
   - Call `Edit(file_path, old_string, new_string)` with `replace_all: false`.
   - On success, record in `apply_log.md` as `<edit_id> OK`.
   - On failure (old_string not found or non-unique), record in `apply_failures.md` as `<edit_id> FAIL — <error>` and continue with the next edit in the same file.
1. After all edits for the file have been attempted, do **not** re-read the file to verify — the harness already errors on failed Edit calls, and re-reads burn context for no added safety. The `apply_log.md` and `apply_failures.md` entries are the authoritative record.

Concurrency: apply is serial. Never fan out Edit calls — concurrent edits to overlapping files cause lost writes. The Phase 2 fan-out covered the heavy cost; Phase 4 is cheap.

## 4.3 Handle apply failures

When an Edit fails:

- `old_string` not found in file → the file changed between Phase 2 proposal and Phase 4 apply (rare: user edited manually between gates), or the proposer hallucinated context. Record and continue.
- `old_string` not unique → the proposer didn't include enough surrounding context to make the match unique. Record and continue.
- File not found → the file was deleted between phases. Record and continue.
- Any other tool error → record with the raw error message and continue.

Do not attempt auto-recovery. A failed edit becomes a follow-up item for the user, not an auto-retry loop.

## 4.4 Write `summary.md`

Final artifact at `.mz/task/<task_name>/summary.md`. Structure:

```
# Batch-Fix Summary

Task: <task_name>
Brief: <verbatim from state.md>
Completed: <ISO timestamp>

## Criteria applied

<numbered list of criteria from criteria.md, each with a count of files it affected>

## Files changed

| file | edits applied | edits failed |
| ---- | ------------- | ------------ |
| ...  | ...           | ...          |

## Files skipped

- <N> DONE_NO_CHANGE — already compliant
- <N> BLOCKED — see skipped.md
- <N> NEEDS_CONTEXT after retry — see skipped.md
- <N> path_outside_repo — see apply_failures.md

## Apply failures

<verbatim contents of apply_failures.md, or "None.">

## Follow-ups

- Review `apply_failures.md` if non-empty.
- Re-run batch-fix with the same brief on failed files after inspection.
- Commit when ready — this skill never commits.
```

### State update at phase exit

- `Phase: 4_complete`
- `Status: completed`
- `Completed: <ISO timestamp>`
- `files_changed: N`
- `edits_applied: N`
- `edits_failed: N`

Emit the final visible block to the user:

```
Batch-fix complete.
  files changed: <N>
  edits applied: <N>
  edits failed: <N>  (see apply_failures.md if > 0)
  files skipped: <N> (see skipped.md)
  summary: .mz/task/<task_name>/summary.md
```
