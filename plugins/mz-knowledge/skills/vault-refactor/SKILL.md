---
name: vault-refactor
description: ALWAYS invoke when renaming a vault note, moving a note to a different folder, or refactoring wikilink references across the vault. Triggers: rename note, move note, vault refactor, update wikilinks.
argument-hint: '<old_name>::<new_name_or_path> [vault path]'
model: opus
allowed-tools: Agent, Read, Write, Grep, Glob, Bash, AskUserQuestion
---

# Vault Refactor

## Overview

Discipline skill that performs a safe rename or move of an Obsidian note with a full reference-graph rewrite across every supported Obsidian Flavored Markdown wikilink form, plus Bases `link()` formulas and quoted YAML frontmatter wikilinks. A rollback manifest capturing every target file's original content is written to the task directory BEFORE any vault file is modified. Two specialist agents split the work: `vault-refactor-scanner` is read-only and enumerates every reference; `vault-refactor-writer` applies the precomputed edits via targeted `Edit` replacements.

## When to Use

- Renaming a permanent or fleeting note to a new claim-style title.
- Moving a note to a different folder (with or without rename).
- Merging-variant: renaming a note into an existing folder structure so referrers update to the new path.

### When NOT to use

- Creating a brand new note — use `process-notes`.
- Deleting a note — do that in the Obsidian app; this skill assumes the note continues to exist under its new name.
- Editing note body content unrelated to the rename — just use `Edit` directly.
- Bulk link cleanup or orphan repair — use `vault-health`.

## Constants

- **TASK_DIR**: `.mz/task/`
- **MAX_REFERENCES_PREVIEW**: 50
- **WIKILINK_FORMS_COUNT**: 12

## Core Process

| Phase | Goal                           | Details                          |
| ----- | ------------------------------ | -------------------------------- |
| 0     | Setup                          | Inline below                     |
| 1     | Scan references                | `phases/scan_references.md`      |
| 1.5   | User approval — affected files | Inline below                     |
| 2     | Rewrite + rollback             | `phases/rewrite_and_rollback.md` |
| 2.5   | Post-write verification        | Inline below                     |

### Phase 0: Setup

1. Parse `$ARGUMENTS` as `<old>::<new>`. If the separator is missing, ask via AskUserQuestion — never guess which half is which.
1. Resolve the vault path from `$ARGUMENTS` suffix, then `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env, then walk up from the current directory until a `.obsidian/` folder is found.
1. Resolve `old` to an existing `.md` file in the vault (basename match). If zero or multiple matches, escalate via AskUserQuestion with the candidates.
1. Collision check: confirm no existing file already matches `new` (same basename in the target folder). If `new` contains a path component, verify the target folder exists or can be created.
1. `task_name = <YYYY_MM_DD>_vault-refactor_<old-slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<old-slug>` is a snake_case summary of the old basename (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. Create `TASK_DIR<task_name>/`.
1. Write `state.md` with `schema_version: 2`, `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <path>`, `OldPath: <path>`, `NewNameOrPath: <value>`, `phase_complete: false`, `what_remains: []`.

### Phase 1.5: User approval — Affected Files

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/references_report.md` and capture its full contents into context.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a normal markdown chat message — every affected file path, the reference count per file (up to `MAX_REFERENCES_PREVIEW`), and the exact before/after text of every proposed replacement. A silent diff is indistinguishable from a broken rename:

```
## References ready for review — vault-refactor

<verbatim contents of .mz/task/<task_name>/references_report.md>

---
**Approve** → proceed to Phase 2 (rewrite + rollback)  ·  **Reject** → abort, state marked aborted_by_user, no vault files modified  ·  reply with feedback to revise
```

Emit the full verbatim contents of `.mz/task/<task_name>/references_report.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the artifact in the question body:

- question: `The references report above is ready for review.`
- options: **Approve** — proceed to Phase 2 (rewrite + rollback) · **Reject** — abort, no vault files modified

**Response handling**:

- **Approve** → update state to `references_approved`, proceed to Phase 2.
- **Reject** → update state to `aborted_by_user` and stop. Do not write the rollback manifest, do not touch vault files.
- **Any other reply (feedback)** → incorporate (e.g., user excludes specific paths, corrects the new name, requests a narrower scope), re-run Phase 1, overwrite `references_report.md`, return to Surface 1, re-read the updated artifact, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2.5: Post-write verification

After `phases/rewrite_and_rollback.md` returns, run `Grep` for the old basename (and, for full-path moves, the old path) across the entire vault, excluding `.obsidian/` and the task directory. Output the Grep result block before concluding — silent verification gets skipped.

- **Zero remaining occurrences** → update state `Status: complete`, `Completed: <ISO timestamp>`, print the verification block, emit `STATUS: DONE`.
- **Any remaining occurrence** → update state `Status: post-write-verification-failed`, print the failing paths and line numbers verbatim, print the rollback manifest path from state, emit `STATUS: BLOCKED` with rollback instructions. Never silently ignore a residual reference.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                     | Rebuttal                                                                                                                                                                                                               |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The bare `[[OldName]]` form is 95% of references — skip the rest." | "The other 5% includes quoted frontmatter wikilinks and Bases `link()` formulas — silent survivors that break the link graph without any visible error. Every form listed in the scanner agent must be scanned."       |
| "Skip the rollback manifest — Git has the previous version."        | "Git is a whole-repo restore. The rollback manifest records the exact pre-edit bytes of every touched vault file, so recovery is a surgical file-by-file replay, not a branch reset that destroys unrelated changes."  |
| "Approve proposals without reading every affected file's preview."  | "Most refactor damage is in the long tail — an aliased heading link, a block reference, a Bases formula. The Phase 1.5 gate shows every proposal for a reason; summary-only approval is how link graphs silently rot." |

## Red Flags

- Writing the rollback manifest after the first vault edit, rather than before.
- Presenting the Phase 1.5 gate with a path or summary instead of the verbatim references report.
- Using `Write` for any per-reference replacement — wholesale rewrites mask corruption; `Edit` fails loudly on drift.
- Proceeding after Phase 2.5 Grep shows remaining occurrences of the old name.
- Renaming the original file before all referrer rewrites complete — creates a window where both old and new are broken.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-refactor verification:
  [ ] references_report.md emitted verbatim as a chat message (Surface 1) and AskUserQuestion selector presented before any write
  [ ] rollback.md written BEFORE first vault edit
  [ ] Every per-reference replacement applied via `Edit` (not `Write`)
  [ ] Original file renamed/moved only after all referrer rewrites succeeded
  [ ] Post-write Grep for old name returned zero occurrences (excluding task dir + .obsidian/)
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

## Error Handling

- **Argument missing separator** → escalate via AskUserQuestion; never guess which half is old vs. new.
- **Old name ambiguous (multiple matches)** → escalate with the candidate list.
- **New name collides with existing file** → escalate with the conflict path; offer rename-into-a-suffix or abort.
- **Scanner returns zero references** → treat as `DONE_WITH_CONCERNS`; surface in Phase 1.5 gate before proceeding — a rename with zero references is legal but suspicious.
- **Writer reports partial failure** → halt; preserve the partially-written vault state; print the rollback manifest path and the list of successfully modified files for manual recovery; emit `STATUS: BLOCKED`.
