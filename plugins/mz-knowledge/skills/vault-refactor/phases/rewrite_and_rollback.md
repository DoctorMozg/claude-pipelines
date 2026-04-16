# Phase 2: Rewrite + Rollback

## Goal

Apply every approved replacement from `references_report.md` to the vault. The rollback manifest is written BEFORE any vault file is modified, so any partial failure is recoverable. Replacements go through `Edit` (targeted string swap that fails loudly on drift); `Write` is reserved for new-folder creation and rollback restoration.

## Step 1: Write the rollback manifest FIRST

Before a single vault file is touched, the orchestrator must capture the pre-edit state of every file that will be modified. This step must complete before Step 2 begins.

1. Read `.mz/task/<task_name>/references_report.md`.

1. Collect the unique set of file paths from the `references:` list — each path appears once regardless of how many references it contains.

1. Also include the old note's own file path (it will be renamed/moved in Step 3).

1. For each unique path:

   - Read the full file contents with the Read tool.
   - Compute a content hash (SHA-256 of the file bytes) to detect post-manifest drift.

1. Write `.mz/task/<task_name>/rollback.md` using exactly this YAML shape:

   ```yaml
   task_name: "<task_name>"
   created_at: <ISO timestamp>
   vault_path: "<absolute vault path>"
   rollback_entries:
     - path: "<absolute path>"
       original_content_hash: "<sha256>"
       original_content: |
         <full file contents, preserved byte-for-byte>
   ```

1. Update `state.md`: `Status: rollback_manifest_written`, `Phase: 2`, `RollbackPath: .mz/task/<task_name>/rollback.md`, `RollbackFileCount: <N>`.

This manifest is a hard precondition for Step 2. If this file does not exist on disk when the writer is dispatched, the writer must refuse to proceed and emit `STATUS: BLOCKED`.

## Step 2: Dispatch `vault-refactor-writer`

Dispatch the `vault-refactor-writer` agent (model: sonnet) with this task-specific prompt:

```
References report: .mz/task/<task_name>/references_report.md
Rollback manifest: .mz/task/<task_name>/rollback.md
Old basename: "<old>"
New value: "<new>"
Vault path: <absolute vault path>
Task dir: .mz/task/<task_name>/
Output path: .mz/task/<task_name>/writer_result.md

Your task:

Apply every replacement declared in the references report. The rollback manifest is a precondition — if it is missing from disk, refuse to proceed and emit STATUS: BLOCKED.

Rules:
- Use the `Edit` tool for every per-reference replacement. `old_string` is the entry's `original` field verbatim; `new_string` is the entry's `replacement` field verbatim.
- Never use `Write` to apply a per-reference replacement — wholesale rewrites mask corruption. `Write` is reserved for new-folder creation (Step 3 of the orchestrator) and rollback restoration.
- Group references by file path. For each file, read once, apply each `Edit` in order, then re-read and verify every replacement is present.
- If `Edit` fails (stale content, `old_string` not found), halt immediately. Record the failure. Do not retry the same Edit on modified input.

Write per-file results to `.mz/task/<task_name>/writer_result.md` using exactly this YAML shape:

total_files: N
total_applied: N
applied:
  - path: "<absolute path>"
    replacements_count: N
    verified: true|false
failures:
  - path: "<absolute path>"
    reason: "<concise explanation>"
    stale_original: "<what Edit expected>"
    actual_content_fragment: "<what the file actually contains near the line>"

Terminal status:
- STATUS: DONE when every reference applied cleanly and every file verified.
- STATUS: DONE_WITH_CONCERNS when some files failed; partial success. The orchestrator will halt and escalate.
- STATUS: BLOCKED if the rollback manifest is missing or unreadable — refuse to apply any edit.
```

## Step 3: Rename or move the original file

After the writer reports `STATUS: DONE`:

1. Read `writer_result.md` to confirm every file in `references_report.md` has been applied and verified.
1. Resolve the new path:
   - If `new_value` contains a path separator, treat it as a vault-relative path. The target folder must exist; if it does not, create it with `Bash mkdir -p <vault>/<target_folder>`.
   - If `new_value` is a bare basename, keep the file in its current folder and change only the filename.
1. Use `Bash mv <old_path> <new_path>` to perform the rename/move atomically at the filesystem level. Do not use `Write` followed by delete — that widens the failure window.
1. Re-read the file at its new path to confirm the move succeeded.
1. Update `state.md`: `Status: original_file_moved`, `NewPath: <new absolute path>`.

If Step 2 reported any failures, skip Step 3 entirely. The writer's partial state and the rollback manifest together preserve enough information for manual recovery — do not compound the problem by moving the source file on top of broken referrers.

## Step 4: Hand off to post-write verification

Return to SKILL Phase 2.5 (inline post-write Grep verification). Do NOT declare the skill complete from this phase — the Grep pass is the final gate.

## Step 5: Update state on success

After Phase 2.5 returns with zero residual occurrences:

```
Status: complete
Phase: 2.5
Completed: <ISO timestamp>
FilesModified: <total_files from writer_result.md>
ReferencesUpdated: <total_applied from writer_result.md>
RollbackPath: .mz/task/<task_name>/rollback.md
OldPath: <original absolute path>
NewPath: <new absolute path>
```

Write `.mz/task/<task_name>/session_summary.md` with the final manifest:

```yaml
task_name: "<task_name>"
completed_at: <ISO timestamp>
old_path: "<original absolute path>"
new_path: "<new absolute path>"
files_modified: N
references_updated: N
rollback_path: ".mz/task/<task_name>/rollback.md"
```

## Error handling

- **Rollback manifest write fails** → halt before Step 2; the skill cannot proceed without a complete manifest. Surface the failure verbatim via AskUserQuestion.
- **Writer `STATUS: DONE_WITH_CONCERNS` (partial apply)** → do NOT proceed to Step 3. Preserve the writer_result.md failure list. Print the rollback manifest path and the failing file paths. Emit `STATUS: BLOCKED` and surface the partial state via AskUserQuestion with manual recovery instructions: `Review .mz/task/<task_name>/rollback.md to restore pre-edit contents for the successfully modified files if you want to abort the rename.`
- **Writer `STATUS: BLOCKED` (rollback manifest missing)** → indicates the Step 1 manifest was not persisted correctly; do not retry the writer until Step 1 is re-run and verified on disk.
- **File `mv` in Step 3 fails** → the referrers have already been updated; use the rollback manifest to restore the referrers if the user chooses to abort. Emit `STATUS: BLOCKED` with the exact `mv` error and the rollback pointer.
- **Phase 2.5 Grep finds residual old name occurrences** → do not silently proceed. Surface every residual occurrence verbatim via AskUserQuestion along with the rollback manifest path.
