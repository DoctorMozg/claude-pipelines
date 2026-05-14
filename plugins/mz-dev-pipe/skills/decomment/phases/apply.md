# Phase 4 — Apply approved edits

Read `edits.json` and apply every edit via the Edit tool. Record success and failure to per-edit logs. Write the final summary report. Never commit.

## Inputs

- `${task_dir}edits.json` (Phase 3 output)
- `state.md` with last gate `diff_approved` (or `auto_approved` when `MZ_DEV_PIPE_AUTO_APPROVE=1` was set)

## Outputs

- `${task_dir}apply_log.md` — `<edit_id> OK` per applied edit
- `${task_dir}apply_failures.md` — `<edit_id> FAIL — <error>` per failed edit
- `${summary_path}` — final summary report at `.mz/reports/<YYYY_MM_DD>_decomment_<slug>.md`

## Steps

### 1. Pre-flight check

Read `state.md`. Assert all of:

- `Status: in_progress`
- Last recorded gate is `diff_approved` or `auto_approved`
- `Phase: 3_complete`

If any assertion fails, abort with an explicit error written to the chat naming the failed assertion. Do not proceed to Edit calls.

Read `${task_dir}edits.json`. Validate:

- Top-level `edits` array exists.
- Every entry has `id`, `file_path`, `old_string`, `new_string`, `rationale`.
- Every `file_path` is absolute (starts with `/`).

If `edits` is an empty array, skip directly to step 4 (write summary) — the report still records the zero-edit run.

If any individual entry fails validation, record it in `apply_failures.md` as `<edit_id> FAIL — <reason>` and continue with the rest.

### 2. Apply edits

Iterate the `edits` array in the order it appears in `edits.json` (which is file-path lexicographic, then `line_start` ascending — set by Phase 3). For each edit:

1. Call the Edit tool with `file_path`, `old_string`, `new_string`. Pass `replace_all: false` explicitly.
1. On success: append `<edit_id> OK` as a new line to `apply_log.md`. Increment the in-memory `edits_applied` counter.
1. On failure (Edit tool error — old_string not found, ambiguous match, file missing, etc.): append `<edit_id> FAIL — <verbatim error message>` as a new line to `apply_failures.md`. Increment the in-memory `edits_failed` counter. Continue with the next edit.

Apply is serial. Do not fan out Edit calls — concurrent edits to the same file cause lost writes, and even cross-file concurrency provides no measurable benefit at the scale this skill operates at.

Do not retry a failed edit. The Edit tool fails verbatim when `old_string` is not unique or not present — those are recorded outcomes, not transient errors. The proposer chose insufficient context; the recorded failure is the answer.

Do not re-read each file after its edits succeed. The Edit tool errors on failed calls; re-reads burn context for no added safety. The `apply_log.md` and `apply_failures.md` entries are the authoritative record.

### 3. Update `state.md`

After the apply loop completes:

- `Phase: 4_complete`
- `Status: completed`
- `edits_applied: <count>`
- `edits_failed: <count>`
- `FilesWritten:` append `apply_log.md`, `apply_failures.md`, `summary.md` to the existing list

### 4. Write summary report

Write to `${summary_path}` (resolved to `.mz/reports/<YYYY_MM_DD>_decomment_<slug>.md` — same date and slug as the task name). Use this template:

```markdown
# Decomment summary — <task_name>

**Date**: <YYYY-MM-DD>
**Scope**: <scope_mode> — <count> files scanned
**Result**: <edits_applied> edits applied, <edits_failed> failed, <files_with_edits> files modified

## Files modified

<bullet list of file paths that received at least one successful edit, sorted lexicographically>

## Failures

<verbatim contents of apply_failures.md as a table, or the literal text "(none)" if no failures>

## Skipped files

<short summary of skipped.md — counts per category and a pointer to the file, or "(none)">

## Follow-ups

- Run project linter / type-checker to verify no syntactic damage.
- Review diff before committing.
- If any failures: inspect `<task_dir>/apply_failures.md` and re-run with feedback if needed.

## Artifacts

- State: `.mz/task/<task_name>/state.md`
- Diff (truncated for display): `.mz/task/<task_name>/diff.md`
- Full edits: `.mz/task/<task_name>/edits.json`
- Apply log: `.mz/task/<task_name>/apply_log.md`
- Apply failures: `.mz/task/<task_name>/apply_failures.md`
```

Always write the summary, even when `edits_applied == 0`. A zero-edit run is still a recorded outcome.

The "Files modified" bullet list is derived from `apply_log.md` by grouping successful edits by `file_path`. A file appears once regardless of how many edits succeeded against it.

### 5. Emit final chat message

After the summary file is written, emit a plain text block to the chat (no AskUserQuestion, no further gating):

```
Decomment complete.
- <edits_applied> edits applied across <files_with_edits> files
- <edits_failed> failures (see <task_dir>/apply_failures.md)
- Summary: <summary_path>

Next: run your linter/type-checker and review the diff before committing.
```

Substitute the actual counts and paths. If `edits_failed` is zero, still emit the failures line so the format is stable — the user can see at a glance that there were zero failures.

## Red Flags

- You called Edit with `replace_all: true` — every edit is intended to target a unique block. Setting `replace_all: true` silently changes meaning and can cascade across the file.
- You aborted the apply loop on the first failure — the loop is best-effort. Failures are recorded in `apply_failures.md` and the loop continues.
- You retried a failed edit — the proposer's `old_string` was insufficient context. That is a recorded outcome, not a retry signal.
- You skipped writing `summary.md` because `edits_applied == 0` — write it anyway. A zero-edit run still records "0 edits applied, scanned N files" and lets the user audit later.
- You committed the changes — this skill never creates commits. The user commits when ready, after their own linter/review pass.
- You wrote to the target files via the Write tool instead of Edit — only Edit calls are permitted in this phase. The Write tool overwrites the entire file and bypasses the surgical-edit contract.
- You used Bash to modify a target file (sed, awk, perl -i) — only Edit calls are permitted. Bash file mutation bypasses the audit trail.

## Verification

- `edits_applied + edits_failed` equals `total_edits` from `state.md` (set in Phase 3).
- Every edit id present in `edits.json` appears in exactly one of `apply_log.md` or `apply_failures.md`.
- The summary file exists at `${summary_path}` with the resolved date and slug substituted into the path.
- No file in the `file_path` set of `edits.json` was touched by anything other than Edit tool calls during this phase.
- `state.md` final state: `Status: completed`, `Phase: 4_complete`, both apply counters populated.
- The final chat message names the summary report path and the failure count.
