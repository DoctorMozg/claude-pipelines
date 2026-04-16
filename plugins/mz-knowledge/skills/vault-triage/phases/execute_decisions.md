# Phase 2: Execute Decisions

## Goal

After the user approved the triage batch in Phase 1.5 (with or without overrides), apply each decision to the vault — promoting, merging, discarding, or deferring — then write a decision log and finalize state.

## Step 1: Parse the approval response

1. Start from the default decision map captured in `.mz/task/<task_name>/triage_batch.md`.
1. If the user replied with plain `approve`, adopt the defaults verbatim — no merge decisions can be present in the defaults because `triage-scorer` leaves `proposed_merge_target: null`. For any default `merge` entry, treat it as a missing-target case and re-ask via AskUserQuestion for the exact target note name per the fallback rule below.
1. If the user replied with an override list (e.g., `1=discard, 3=merge::Target Note Name`), parse each `index=decision` pair:
   - The index is 1-based and binds to the ordered `decisions` list in `triage_batch.md`.
   - The decision must be one of `promote | merge | discard | defer`.
   - For `merge`, the syntax is `merge::<target note name>`. If the user wrote just `merge` without `::target`, that individual decision is incomplete — do not apply it. Re-ask only for the missing target via AskUserQuestion: `Note at index <N> ("<title>") needs a merge target. Reply with the exact target note name (no path, no brackets).` Accept the reply as the target.
1. Record the resolved decision map in `state.md` under `ResolvedDecisions:` as a YAML block keyed by path.

## Step 2: Apply decisions

Process the batch in order. For each note, execute the decision and record the outcome to `state.md`.

### promote

1. Read the inbox note in full.
1. Compute the source hash: SHA-256 of the file's pre-operation content. Record in the decision log (Step 3).
1. Patch frontmatter:
   - Set `type: permanent`.
   - Keep `status: draft`.
   - Remove the `inbox` tag from the `tags:` list. If `tags:` becomes empty, drop the key entirely.
   - If `created:` is absent, add `created: <today's YYYY-MM-DD>`.
   - Preserve every other existing frontmatter field verbatim.
1. Compute the destination path: `<vault>/<PERMANENT_FOLDER>/<original filename>` where `PERMANENT_FOLDER` is read from `state.md`.
1. If the destination already exists, append `-2`, `-3`, ... before `.md` until the path is free.
1. Write the patched content to the destination path.
1. Delete the inbox source file only after the destination write is verified by re-reading it.

### merge

1. Resolve the target: if the user supplied a path, use it. If the user supplied a bare title, Glob `<vault>/**/*.md` (excluding `.obsidian/`) for a file whose basename without `.md` matches the title case-insensitively. If zero or multiple candidates match, re-ask via AskUserQuestion for the exact path.

1. Read the source inbox note and the target note.

1. Compute the source hash (SHA-256 of pre-operation inbox file). Record in the decision log.

1. Extract the source body (everything after the closing `---` of its frontmatter) and source title.

1. Append to the target note's body:

   ```


   ## Merged from <source title>

   <source body>
   ```

1. Write the merged content back to the target note.

1. Delete the inbox source file only after the target write is verified.

### discard

1. Read the inbox file once to compute the SHA-256 source hash (for the decision log and recoverability).
1. Delete the inbox file. No further confirmation — the user approved the discard in Phase 1.5.

### defer

1. Compute the new review date: `<today + FLEETING_AGE_DAYS_DEFER_THRESHOLD days>` formatted as `YYYY-MM-DD`. Use `FLEETING_AGE_DAYS_DEFER_THRESHOLD` from SKILL constants (14).
1. Compute the source hash (SHA-256 of pre-operation content). Record in the decision log.
1. Patch frontmatter: set `review_after: <computed date>`. Preserve every other frontmatter field verbatim.
1. Write the patched content back to the same inbox path. The file stays in the inbox.

## Step 3: Write the decision log

Write `.mz/task/<task_name>/decision_log.md` as YAML:

```yaml
task_name: <task_name>
executed_at: <ISO timestamp>
entries:
  - path: "<original inbox path>"
    title: "<note title>"
    decision: promote|merge|discard|defer
    source_sha256: "<64-char hex hash of pre-operation file content>"
    outcome_path: "<destination path for promote/merge, or null for discard, or same path for defer>"
    merge_target: "<target note path, only for merge; null otherwise>"
    notes: "<one-line descriptor — e.g., 'collision resolved to -2', 'tags emptied', or empty>"
  - ...
summary:
  promote: N
  merge: N
  discard: N
  defer: N
  total: N
```

The `source_sha256` field is load-bearing for recoverability — if the user asks to undo a discard or promote, the hash lets them verify the exact pre-operation content in filesystem snapshots or git history before attempting recovery.

## Step 4: Update state to terminal

Update `state.md`:

```
Status: complete
Phase: 2
Completed: <ISO timestamp>
Promoted: N
Merged: N
Discarded: N
Deferred: N
DecisionLog: .mz/task/<task_name>/decision_log.md
```

## Step 5: Print the verification block

```
vault-triage complete:
  Batch size: N
  Promoted: N   (→ <PERMANENT_FOLDER>)
  Merged: N     (→ target notes listed in decision_log.md)
  Discarded: N
  Deferred: N   (review_after stamp applied)
  Decision log: .mz/task/<task_name>/decision_log.md
  Task dir: .mz/task/<task_name>/
```

## Constraints

- Never skip the SHA-256 hash step. `decision_log.md` is the recoverability record; without source hashes a user cannot verify undo attempts.
- Never auto-pick a merge target. Every `merge` must carry a user-supplied target before this phase applies it.
- Never overwrite an existing permanent-notes file on `promote`. Resolve collisions with `-2`, `-3`, ... suffixes.
- Never delete an inbox source file before the destination write (promote or merge) is verified by re-read.
- Never modify frontmatter fields that the decision rules do not touch. `promote` and `defer` are narrow patches, not rewrites.
- Never prompt the user mid-batch for any decision other than the `merge::<target>` missing-target fallback in Step 1.
