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
1. Derive `task_name = process-notes_<slug>_<HHMMSS>` and create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `VaultClaude: <path or none>`.

### Phase 1.5: User Approval — Proposed Atomic Notes

**This orchestrator** (not a subagent) must present proposals to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/proposals.md` in full. Present the full verbatim contents of `proposals.md` — a numbered list of proposed notes, each with its claim-style title and core idea. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

```
Proposed atomic notes (N from your input):

1. "<Claim-style title here>"
   Core: One-sentence summary of the single idea...

2. "<Second title>"
   Core: ...

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

Response handling:

- **"approve"** → update state to `drafts_approved`, proceed to Phase 2 with all notes.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Number list** (e.g. `1,3`) → mark those note numbers as skipped, proceed to Phase 2 with the remaining set.
- **Feedback** → pass feedback to the atomization-proposer, re-run Phase 1, re-present **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2.5: User Approval — Proposed Links

**This orchestrator** (not a subagent) must present link proposals to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/link_proposals.md` in full. Present the full verbatim contents of `link_proposals.md` — proposed links grouped per new note with the relationship type and reason. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

```
Proposed links for <N> new notes:

"<Note Title>" should link to:
  → [[Existing Note]] — <relationship: extends|supports|contradicts|example-of|prerequisite-for|see-also>
    Reason: one sentence...

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

Response handling:

- **"approve"** → update state to `links_approved`, write all links, proceed to completion.
- **"reject"** → update state to `aborted_by_user` for links (notes already written in Phase 2 remain on disk without links).
- **Feedback** → skip specified links, accept the rest, re-present **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves. Never write links without explicit approval.

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
