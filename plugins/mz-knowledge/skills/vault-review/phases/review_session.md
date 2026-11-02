# Phase 2: Review Session

## Goal

Walk the user through each note in the approved queue. Update `last_reviewed` only for notes the user confirms reviewing. Never auto-archive or auto-promote without explicit instruction.

## Process

Read `<PROJECT_ROOT>/.mz/task/<task_name>/review_queue.md` and iterate through each entry in order.

### For each note in the queue

1. Read the note file from its `path`.

1. **Surface 1 — emit the note review message.** Output the note contents verbatim as a normal markdown chat message:

```
## Note review — vault-review (<N>/<M>)

## [[<Note Title>]]
<first 300 words of note body>

Maturity: <seedling|sapling|tree|ancient-tree> | last_reviewed: <date or never> | outlinks: <N> | inlinks: <N> | score: <X>

---
**Done** → mark reviewed  ·  **Skip** → leave unchanged  ·  **Promote** → advance maturity  ·  **Archive** → flag for end-of-session archival  ·  type a change to apply it (Edit)  ·  type `abort` to stop the session
```

1. **Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the note content in the question body. AskUserQuestion takes at most four options, so Edit and Abort are typed replies, listed in the Surface 1 footer:

   - question: `Note <N>/<M> above is ready for your action.`
   - options:
     - **Done** — mark as reviewed and update last_reviewed to today
     - **Skip** — leave the note unchanged
     - **Promote** — advance maturity one stage (seedling→sapling→tree→ancient-tree)
     - **Archive** — flag for archiving at end of session

1. Handle the response:

- **Done** → update the note's frontmatter: set `last_reviewed: <today ISO date>`. Preserve all other frontmatter keys and the body untouched. Continue to the next note.
- **Skip** → append `- title: "<title>" action: skipped` to `<PROJECT_ROOT>/.mz/task/<task_name>/session_log.md`. Do not touch the note file. Continue.
- **Promote** → advance `maturity` one stage: `seedling → sapling → tree → ancient-tree`. If the note is already `ancient-tree`, report that and re-present with Done or Skip as the choices. Update `last_reviewed: <today>` alongside the maturity change. Continue.
- **Archive** → do not move the file mid-session. Append `- title: "<title>" path: "<path>" action: archive_pending` to `<PROJECT_ROOT>/.mz/task/<task_name>/session_log.md`. Continue. Archive moves are batched at the end.
- **Typed reply `abort`** (any case) → update `state.md`: `Status: aborted_by_user`, `Phase: 2`, `NotesReviewed: <count so far>`. Stop. Skip the summary step.
- **Any other typed reply (Edit)** → treat the text as the change to make. Apply it via `Edit` to the note body (never the frontmatter unless the change specifically targets it). Re-read the file. Re-emit the note review message (Surface 1) and re-present the selector (Surface 2) — the user then replies Done, Skip, or another change.

All frontmatter writes must preserve YAML key order and existing keys. If the note has no frontmatter block, create one at the top with only `last_reviewed:` (and `maturity:` for `promote`).

### After the queue is exhausted

1. Count outcomes from `session_log.md`: `reviewed`, `skipped`, `promoted`, `archive_pending`.
1. Write `<PROJECT_ROOT>/.mz/task/<task_name>/session_summary.md`:

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

3. Update `state.md`: `Phase: 2` plus the totals above. If `archive_pending` is 0, also set `Status: complete`, `Completed: <ISO timestamp>`, `phase_complete: true`, `what_remains: []`, and go straight to the final summary below. Otherwise keep `Status: running` until that gate resolves.

### Archive confirmation (only if any `archive_pending`)

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/session_log.md` and collect every `archive_pending` entry.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: archive gate]`; `Status` stays `running`.

**Surface 1 — emit the archive confirmation message.** Output the list verbatim as a normal markdown chat message:

```
## Archive confirmation — vault-review

<N> notes flagged for archive:

1. [[Title]] — <path>
2. [[Title]] — <path>
...

---
**Approve** → move all flagged notes to <vault>/archive/  ·  **Reject** → leave all notes in their current locations  ·  reply with note numbers (e.g. 1,3) to archive a subset
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the list in the question body:

- question: `The archive list above is ready for confirmation.`
- header: `Archive`
- options:
  - **Approve** — move all flagged notes to `<vault>/archive/`
  - **Reject** — leave all notes in their current locations

**Response handling**:

- **Approve** → add `- archive approved: .mz/task/<task_name>/session_log.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, set `Phase: archive_approved`, then for each flagged note move the file to `<vault>/archive/` (create the folder if absent). Preserve filename. Update `session_log.md` action to `archived`.
- **Reject** → leave all notes in place. Update `session_log.md` action to `archive_cancelled` for each flagged entry.
- **Any other reply (number list)** → archive only the listed entries; leave the rest. Update `session_log.md` accordingly.
- **No answer** → set `Status: blocked`, keep `awaiting approval: archive gate`, stop. A missing answer is never approval.

After archive handling, set `Status: complete`, `Completed: <ISO timestamp>`, `phase_complete: true`, `what_remains: []`, and print the final summary:

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
- **Typed change yields no edit** (empty or unclear text) → re-prompt once; if still empty, treat as `skip`.
