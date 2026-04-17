---
name: vault-connect
description: "ALWAYS invoke when finding missing wikilinks for a note, suggesting connections between notes, discovering which vault notes should link to the current note, or improving a note's link density. Triggers: link notes, suggest wikilinks, find connections, improve link density."
argument-hint: <note name or path to find links for>
model: sonnet
allowed-tools: Agent, Read, Write, Grep, Glob, AskUserQuestion
---

# Vault Connect

## Overview

Discipline skill that finds existing vault notes that should be linked to or from a given note. Dispatches `link-suggester` to search by keyword and title mentions, then uses typed relationship labels (`supports`, `contradicts`, `extends`, `example-of`, `prerequisite-for`, `see-also`) for each proposed link. All wikilinks require explicit user approval before being written. Writes wikilinks in-body where topically appropriate, or in a `## Related` section otherwise.

## When to Use

- After adding a new permanent note.
- When a note feels isolated from the rest of the vault.
- During a review session when a note has zero outlinks.
- Surfacing "hidden" connections across distant topics.

### When NOT to use

- Immediately after `process-notes` on the same note — link suggestions are already part of that pipeline.
- For semantic search or content retrieval — use direct `Grep`/`Read` or an MCP-based search tool.
- For note content editing unrelated to links — just use `Edit` directly.

## Constants

- **MAX_OUTBOUND_LINKS**: 5
- **MAX_INBOUND_LINKS**: 3
- **TARGET_PREVIEW_WORDS**: 500
- **MATCH_PREVIEW_WORDS**: 200
- **MAX_CANDIDATES_READ**: 15
- **TASK_DIR**: `.mz/task/`

## Core Process

| Phase | Goal            | Details                       |
| ----- | --------------- | ----------------------------- |
| 0     | Setup           | Inline below                  |
| 1     | Find candidates | `phases/find_candidates.md`   |
| 1.5   | User approval   | Inline below                  |
| 2     | Write links     | `phases/suggest_and_write.md` |

### Phase 0: Setup

1. Resolve the target note from `$ARGUMENTS`. If it is a path, `Read` the file directly. If it is a note name, glob the vault for `<name>.md` — if zero or multiple matches, escalate via AskUserQuestion with the candidates.
1. If `$ARGUMENTS` is empty, ask the user via AskUserQuestion which note to connect — never guess.
1. Resolve the vault path from `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env, then the target note's parent directory tree (walk up until a `.obsidian/` folder is found).
1. `task_name` = `vault-connect_<note-slug>_<HHMMSS>` where `<note-slug>` is a snake_case summary of the note title (max 20 chars) and `<HHMMSS>` is wall-clock time.
1. Create `TASK_DIR<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <path>`, `Target: <path>`.

### Phase 1.5: User approval — Proposed Links

**This orchestrator** (not a subagent) must present link proposals to the user via AskUserQuestion. This step is interactive and must not be delegated.

Read `.mz/task/<task_name>/link_proposals.md` in full. Present the full verbatim contents of `link_proposals.md` — proposals grouped by direction, each labelled with a letter for skip-list responses. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Format:

```
Proposed links for [[<target title>]]:

Links to add to this note (outbound):
  a. → [[Existing Note A]] — extends
     Why: <one sentence>
  b. → [[Existing Note B]] — prerequisite-for
     Why: <one sentence>

Notes that should link back (inbound):
  c. → [[Existing Note C]] — example-of
     Why: <one sentence>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

Response handling:

- **"approve"** → update state to `links_approved`, proceed to Phase 2 with all proposals.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Letter list** (e.g. `a,c`) → mark those proposals as skipped, proceed to Phase 2 with the remaining set.
- **Feedback** → pass feedback to `link-suggester`, re-run Phase 1, return to this gate, re-present **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves. Never write links without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                     | Rebuttal                                                                                                                                                                       |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "The note has plenty of links already, skip this."  | "Link quantity is not link quality — vault-connect finds typed relationships (`prerequisite-for`, `contradicts`) that generic backlinking tools and casual linking miss."      |
| "Just add all suggested links, no need to approve." | "Auto-wikilinks create false relationships when context is superficial; typed relationship proposals force articulation of WHY two notes connect, which is where value lives." |
| "I'll do this manually later."                      | "Link suggestions carry full context at write time; manual linking requires re-reading both notes; it will not happen later. The unlinked note is the Zettelkasten failure."   |

## Red Flags

- Writing wikilinks before presenting them to the user.
- Proposing links based on shared keywords alone without checking topical alignment.
- Adding wikilinks to the note's frontmatter `links:` property instead of in-body.
- Proceeding to Phase 2 without explicit "approve" from the user.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-connect verification:
  [ ] Proposals shown via AskUserQuestion before any write
  [ ] All written links use [[wikilink]] syntax, not [text](path) markdown
  [ ] Outbound and inbound links placed in-body or in a ## Related section
  [ ] state.md Status is `completed` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## Error Handling

- **Target note not found or ambiguous** → escalate via AskUserQuestion with the candidate list; never guess.
- **Vault path unresolvable** → escalate via AskUserQuestion; never guess a substitute path.
- **`link-suggester` returns empty proposals** → report the empty result to the user via AskUserQuestion with the option to broaden search or abort — do not silently write nothing and claim success.
- **Vault has fewer than 10 readable notes** → accept `DONE_WITH_CONCERNS` from the agent, surface the small-vault concern in the approval gate.
