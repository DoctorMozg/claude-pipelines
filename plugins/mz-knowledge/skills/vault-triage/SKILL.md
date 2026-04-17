---
name: vault-triage
description: 'ALWAYS invoke when triaging inbox fleeting notes in a fast batch with promote/merge/discard/defer decisions. Triggers: triage inbox, fleeting review, clear inbox, batch decide.'
argument-hint: '[vault path]'
model: sonnet
allowed-tools: Agent, Read, Write, Bash, Glob, AskUserQuestion
---

# Vault Triage

## Overview

Discipline skill that runs a 30-second triage pump over a small batch of fleeting inbox notes. The `triage-scorer` agent scores each note with a deterministic heuristic ladder and proposes a default decision from a closed vocabulary (`promote | merge | discard | defer`). The user accepts the defaults wholesale or overrides individual decisions. Merge targets are never chosen by the agent — the user names them explicitly.

## When to Use

- Weekly inbox review to clear backlog after bursty capture sessions.
- Post-capture cleanup when several fleeting notes have accumulated.

### When NOT to use

- Editing a single known note — use `Edit` directly.
- Atomizing a long fleeting note into multiple permanent notes — use `process-notes`.
- Proposing `[[wikilinks]]` between existing notes — use `vault-connect`.

## Constants

- **TASK_DIR**: `.mz/task/`
- **BATCH_SIZE**: 7
- **INBOX_FOLDER**: `inbox/`
- **FLEETING_AGE_DAYS_DEFER_THRESHOLD**: 14
- **STUB_WORD_THRESHOLD**: 20

## Core Process

| Phase | Goal                      | Details                       |
| ----- | ------------------------- | ----------------------------- |
| 0     | Setup                     | Inline below                  |
| 1     | Score batch               | `phases/score_batch.md`       |
| 1.5   | User approval — decisions | Inline below                  |
| 2     | Execute decisions         | `phases/execute_decisions.md` |

### Phase 0: Setup

1. **Resolve the vault path.** Resolve the vault path with precedence: `$ARGUMENTS` → `OBSIDIAN_VAULT_PATH` env → `MZ_VAULT_PATH` env → walk up from cwd to the nearest `.obsidian/` directory.

1. **Resolve the permanent-notes folder.** Read `<vault>/CLAUDE.md`. Extract the permanent-notes folder name from it (e.g., `04 - Permanent/`). If `CLAUDE.md` is absent or does not declare the permanent-notes folder, ask the user via AskUserQuestion: `What is your vault's permanent-notes folder path (relative to vault root)?` Store the answer in `state.md` under the key `PERMANENT_FOLDER`. Never hardcode a fallback path.

1. **Resolve the batch.** Glob `<vault>/<INBOX_FOLDER>/*.md` sorted by mtime ascending; take the first `BATCH_SIZE` notes. If zero notes are found, update `state.md` to `Status: empty_inbox` and tell the user the inbox is empty, then stop.

1. **Create the task directory.** Derive `task_name = vault-triage_<slug>_<HHMMSS>` where `<slug>` is a short mode tag (e.g., `weekly`) and `<HHMMSS>` is wall-clock time. Create `TASK_DIR<task_name>/` on disk. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <absolute path>`, `PERMANENT_FOLDER: <resolved path>`, `BatchPaths: <list of absolute paths>`.

### Phase 1.5: User approval — Triage Decisions

**This orchestrator** (not a subagent) must present the triage proposals to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/triage_batch.md` in full and capture its contents into the orchestrator's context. Present the full verbatim contents of `triage_batch.md` — each note's title, preview, proposed decision, and rationale. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Triage batch ready for review**
Inbox batch of N notes scored and proposed for triage decisions (promote/merge/discard/defer).

- **Approve** → proceed to Phase 2 and execute all proposed decisions
- **Reject** → abort the triage session, no vault changes
- **Feedback** → override individual decisions and re-present for approval
```

Format the question body as:

```
Triage batch ready for review (N notes).

<verbatim contents of triage_batch.md>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

The user may also reply with an override list such as `1=discard, 3=merge::Target Note Name`. Each override binds to the note's index in the batch.

Response handling:

- **"approve"** → update state to `decisions_approved`, proceed to Phase 2 with the default decision map from `triage_batch.md`.
- **"reject"** → update state to `aborted_by_user` and stop.
- **Feedback or override list** → apply overrides to the decision map and re-present via AskUserQuestion, OR proceed with the user-supplied override map if the user's reply is an explicit override list. For any `merge` decision in the override list, require `merge::<target note name>` syntax; if the user writes just `merge` without a target, re-ask for the missing target via AskUserQuestion. This is a loop — repeat until explicit approval. Never proceed to Phase 2 without the user's explicit approval or an unambiguous override map.

## Decision Vocabulary

- **promote** — move the note from the inbox folder to the permanent-notes folder and patch frontmatter.
- **merge** — append the note's body to a user-named target note, then delete the inbox source.
- **discard** — delete the inbox file.
- **defer** — stamp a `review_after` frontmatter field and keep the note in the inbox.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                   | Rebuttal                                                                                                                               |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| "Auto-discard all stubs without showing them to the user."        | "Even stubs might represent intentional micro-notes; every discard must be approved."                                                  |
| "Pick the merge target automatically from the most-similar note." | "Merge target requires user intent; the agent proposes, the user names the target."                                                    |
| "Process the whole inbox in one pass, don't cap at 7."            | "`BATCH_SIZE = 7` keeps each session under 30 seconds; larger batches cause decision fatigue and erode the quality of every decision." |

## Red Flags

- Applying any decision before Phase 1.5 approval — all vault writes are gated.
- Auto-selecting a merge target instead of leaving `proposed_merge_target: null` and requiring the user to name it.
- Processing more than `BATCH_SIZE` (7) notes in a session — batching prevents decision fatigue.
- Deleting an inbox source file before verifying the destination write on promote or merge.
- Proceeding to Phase 2 without explicit "approve" from the user at Phase 1.5.

## Verification

Verification: delegated to phase files — see Phase Overview table above.
