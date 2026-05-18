---
name: process-notes
description: ALWAYS invoke when processing fleeting notes into permanent atomic notes, atomizing long notes, running the fleeting-to-permanent pipeline, or converting raw captures into vault-ready notes.
argument-hint: '<note name, daily note date YYYY-MM-DD, #fleeting tag, or paste raw text>'
model: opus
allowed-tools: Agent, Read, Write, AskUserQuestion
---

# Process Notes

## Overview

Discipline skill that runs the fleeting-to-permanent pipeline with explicit approval gates. Takes raw input (a fleeting note, a daily note, or pasted text), proposes atomic splits with claim-style titles, drafts each note, writes approved drafts to the vault, and suggests `[[wikilinks]]` to existing notes — all with explicit user approval before any write and before any link is added. Enforces claim-style titles (sentence asserting one idea), `status: draft` frontmatter on every new note, and vault CLAUDE.md conventions for folder placement, frontmatter schema, and tag taxonomy.

## When to Use

- Processing inbox or `#fleeting` tagged notes into permanent atomic notes.
- Atomizing long, multi-idea notes into separately linkable atomic notes.
- Converting daily notes, highlights, or pasted raw captures into vault-ready notes.

### When NOT to use

- Quick single-note editing — just use `Edit` directly.
- Vault maintenance (orphan detection, broken links, frontmatter sweeps) — use `vault-health`.
- Link suggestions for notes that already exist in the vault — use `vault-connect`.

## Constants

- **MAX_ATOMIC_NOTES_PER_RUN**: 10 (if input would produce more, ask the user to split input first)
- **MIN_INPUT_WORDS**: 100 (below this, input is likely already atomic — confirm before atomizing)
- **MAX_INPUT_WORDS_PER_PASS**: 2000 (quality degrades above this cap)
- **MAX_LINKS_PER_NOTE**: 5 (cap on link suggestions per new note)
- **MAX_TITLE_CHARS**: 70
- **MAX_FILENAME_CHARS**: 60
- **TASK_DIR**: `.mz/task/`

## Core Process

| Phase | Goal                   | Details                       |
| ----- | ---------------------- | ----------------------------- |
| 0     | Setup                  | Inline below                  |
| 1     | Atomize & Draft        | `phases/atomize_and_draft.md` |
| 1.5   | User approval — drafts | Inline below                  |
| 2     | Link & Write           | `phases/link_and_write.md`    |
| 2.5   | User approval — links  | Inline below                  |

### Phase 0: Setup

1. Read vault CLAUDE.md if present at the vault root — extract folder structure, frontmatter schema, naming conventions, and tag taxonomy.
1. Resolve input: if the argument is a note name, Read the note. If it matches `YYYY-MM-DD`, try `<vault>/daily/YYYY-MM-DD.md`. If it is raw text, use directly.
1. If the resolved input is empty, ask the user what to process via AskUserQuestion — never guess.
1. Derive `task_name = <YYYY_MM_DD>_process-notes_<slug>` where `<YYYY_MM_DD>` is today's date (underscores); on same-day collision append `_v2`, `_v3`. Create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `schema_version: 2`, `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `VaultClaude: <path or none>`, `phase_complete: false`, `what_remains: []`.

### Phase 1.5: User Approval — Proposed Atomic Notes

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/proposals.md` and capture the full contents into context.

**Surface 1 — emit the plan message.** Output the proposals verbatim as a normal markdown chat message:

```
## Proposals ready for review — process-notes

<verbatim contents of .mz/task/<task_name>/proposals.md>

---
**Approve** → proceed to Phase 2, write all approved notes with links  ·  **Reject** → abort, discard proposals, do not write  ·  reply with feedback to revise (or a number list like `1,3` to skip specific notes)
```

Emit the full verbatim contents of `.mz/task/<task_name>/proposals.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the proposals in the question body, they live in the plan message above:

- question: `The proposed atomic notes above are ready for review.`
- options:
  - **Approve** — proceed to Phase 2, write all notes with links
  - **Reject** — abort, discard proposals, do not write

Response handling:

- **Approve** → update state to `drafts_approved`, proceed to Phase 2 with all notes.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Number list** (e.g. `1,3`) → mark those note numbers as skipped, proceed to Phase 2 with the remaining set.
- **Any other reply (feedback)** → pass feedback to the atomization-proposer, re-run Phase 1, overwrite `.mz/task/<task_name>/proposals.md`, return to this gate, re-read the updated proposals, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2.5: User Approval — Proposed Links

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/link_proposals.md` and capture the full contents into context.

**Surface 1 — emit the plan message.** Output the link proposals verbatim as a normal markdown chat message:

```
## Link proposals ready for review — process-notes

<verbatim contents of .mz/task/<task_name>/link_proposals.md>

---
**Approve** → write all proposed links and complete the task  ·  **Reject** → abort link writing, notes remain unlinked  ·  reply with feedback to revise (or a number list like `1,3` to skip specific links)
```

Emit the full verbatim contents of `.mz/task/<task_name>/link_proposals.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the link proposals in the question body, they live in the plan message above:

- question: `The proposed links above are ready for review.`
- options:
  - **Approve** — write all proposed links and complete the task
  - **Reject** — abort link writing, notes remain unlinked

Response handling:

- **Approve** → update state to `links_approved`, write all links, proceed to completion.
- **Reject** → update state to `aborted_by_user` for links (notes already written in Phase 2 remain on disk without links).
- **Number list** (e.g. `1,3`) → mark those link numbers as skipped, proceed with the remaining set.
- **Any other reply (feedback)** → skip specified links or apply feedback, re-present the updated set. Return to Surface 1, re-read `.mz/task/<task_name>/link_proposals.md`, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never write links without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                | Rebuttal                                                                                                                                                                                                                |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Just write the notes without proposing first, it'll be fine." | "Atomization is heuristic — wrong splits create orphaned fragments that never get linked, and missed splits bury compound ideas that AI cannot surface later. The gate costs seconds, the miss costs the note forever." |
| "Use topic-style titles like 'Habits' — they're cleaner."      | "Topic titles are folders, not ideas. 'Variable reward schedules drive habit persistence' is searchable, linkable, and tells you what the note argues without opening it."                                              |
| "Skip the link step — I'll add links later."                   | "Links added at write time carry context; links added later require re-reading every note. The Zettelkasten failure mode is unlinked notes — the linking step is where connections actually happen."                    |

## Red Flags

- Writing notes to the vault without presenting proposals first.
- Using topic-style titles (`"Habits"`, `"Leadership"`) instead of claim-style assertions (`"Variable rewards drive habit formation"`).
- Writing notes without `status: draft` frontmatter.
- Processing more than `MAX_INPUT_WORDS_PER_PASS` words in a single atomization pass — quality degrades, split the input first.
- Proceeding to Phase 2 without explicit "approve" from the user.

## Verification

Print this block before concluding — silent checks get skipped:

```
process-notes verification:
  [ ] Proposals shown via AskUserQuestion before any write
  [ ] All written notes carry `status: draft` frontmatter
  [ ] All titles are claim-style assertions (no bare topics)
  [ ] Link proposals shown via AskUserQuestion before any link was written
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.
