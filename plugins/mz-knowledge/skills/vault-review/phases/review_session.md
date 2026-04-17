# Phase 2: Review Session

## Goal

Walk the user through each note in the approved queue. Update `last_reviewed` only for notes the user confirms reviewing. Never auto-archive or auto-promote without explicit instruction.

## Process

Read `.mz/task/<task_name>/review_queue.md` and iterate through each entry in order.

### For each note in the queue

1. Read the note file from its `path`.
1. Before invoking AskUserQuestion, emit a text block to the user:

```
**Note Review — <N>/<M>**
Review this note and choose an action. You can update its maturity, make edits, or skip.

- **Done** → mark as reviewed and update last_reviewed to today
- **Skip** → leave the note unchanged
- **Edit** → describe a change, I will apply it and re-prompt
- **Promote** → advance maturity one stage (seedling→sapling→tree→ancient-tree)
- **Archive** → flag for archiving at end of session
- **Abort** → stop the session now
```

1. Invoke AskUserQuestion with:

```
Reviewing note <N>/<M>:

## [[<Note Title>]]
<first 300 words of note body>

Maturity: <seedling|sapling|tree|ancient-tree> | last_reviewed: <date or never> | outlinks: <N> | inlinks: <N> | score: <X>

Type **Done**, **Skip**, **Edit**, **Promote**, **Archive**, or **Abort**.
```

3. Handle the response:

- **`done`** → update the note's frontmatter: set `last_reviewed: <today ISO date>`. Preserve all other frontmatter keys and the body untouched. Continue to the next note.
- **`skip`** → append `- title: "<title>" action: skipped` to `.mz/task/<task_name>/session_log.md`. Do NOT touch the note file. Continue.
- **`edit`** → ask the user to describe the change. Apply it via `Edit` to the note body (never the frontmatter unless the change specifically targets it). Re-read the file. Re-present the note with the same AskUserQuestion — the user then replies `done`, `skip`, or another `edit`.
- **`promote`** → advance `maturity` one stage: `seedling → sapling → tree → ancient-tree`. If the note is already `ancient-tree`, report that and ask for `done` or `skip` instead. Update `last_reviewed: <today>` alongside the maturity change. Continue.
- **`archive`** → do NOT move the file mid-session. Append `- title: "<title>" path: "<path>" action: archive_pending` to `.mz/task/<task_name>/session_log.md`. Continue. Archive moves are batched at the end.
- **`abort`** → update `state.md`: `Status: aborted_mid_session`, `Phase: 2`, `NotesReviewed: <count so far>`. Stop. Skip the summary step.

All frontmatter writes must preserve YAML key order and existing keys. If the note has no frontmatter block, create one at the top with only `last_reviewed:` (and `maturity:` for `promote`).

### After the queue is exhausted

1. Count outcomes from `session_log.md`: `reviewed`, `skipped`, `promoted`, `archive_pending`.
1. Write `.mz/task/<task_name>/session_summary.md`:

```yaml
mode: <mode>
completed_at: <ISO timestamp>
totals:
  reviewed: <N>
  skipped: <N>
  promoted: <N>
  archive_pending: <N>
entries:
  - title: "Note Title"
    path: "<absolute path>"
    action: reviewed|skipped|promoted|archive_pending
    notes: "optional note on promote new maturity or edit description"
```

3. Update `state.md`: `Status: completed`, `Phase: 2`, `Completed: <ISO timestamp>`, plus the totals above.

### Archive confirmation (only if any `archive_pending`)

Before invoking AskUserQuestion, emit a text block to the user:

```
**Archive Confirmation**
<N> notes are pending archival. Review the list and approve to move them to the archive folder, or reject to keep them in place.

- **Approve** → move all flagged notes to <vault>/archive/
- **Reject** → leave all notes in their current locations
- **Selective** → specify note numbers (e.g. 1,3) to archive only those
```

Invoke AskUserQuestion with:

```
<N> notes flagged for archive:

1. [[Title]] — <path>
2. [[Title]] — <path>
...

Type **Approve** to move all to <vault>/archive/, **Reject** to cancel, or type numbers (e.g. 1,3) to archive a subset.
```

Response handling:

- **`approve`** → for each flagged note, move the file to `<vault>/archive/` (create the folder if absent). Preserve filename. Update `session_log.md` action to `archived`.
- **`reject`** → leave all notes in place. Update `session_log.md` action to `archive_cancelled` for each flagged entry.
- **Number list** → archive only listed entries; leave the rest. Update `session_log.md` accordingly.

After archive handling, print the final summary:

```
vault-review complete:
  Mode: <mode>
  Reviewed: <N>    Skipped: <N>
  Promoted: <N>    Archived: <N>
  Task dir: .mz/task/<task_name>/
```

## Error handling

- **Note file moved or deleted since scan** → skip the entry, log `action: missing` in `session_log.md`, continue without interrupting the session.
- **Frontmatter malformed** (unparseable YAML) → report the exact parse error to the user via AskUserQuestion before writing; offer to skip or have the user fix the block manually.
- **Edit response yields no change** (empty input) → re-prompt once; if still empty, treat as `skip`.
