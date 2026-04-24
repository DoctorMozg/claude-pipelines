---
name: vault-review
description: ALWAYS invoke when starting a knowledge review session, surfacing notes to review, checking which notes are due for review, or running the weekly/monthly review ritual.
argument-hint: '[optional: review mode — daily|weekly|monthly, or leave empty for smart queue]'
model: sonnet
allowed-tools: Agent, Read, Write, Glob, Grep, AskUserQuestion
---

# Vault Review

## Overview

Discipline skill that builds a composite review queue ranking notes by: days since last review (`last_reviewed` frontmatter), backlink density (notes with zero outlinks score highest), maturity stage (`maturity` frontmatter: seedling > sapling > tree > ancient-tree), and linked-note recency (notes connected to recently modified notes surface first). Surfaces 5-10 notes per session. Updates `last_reviewed` frontmatter on completion. Dispatches `moc-gap-detector` to surface structural gaps alongside the review.

## When to Use

- Starting a review session.
- Checking which permanent notes need attention.
- Running the daily/weekly/monthly review ritual.

### When NOT to use

- For vault maintenance (orphans, broken links, stale sweeps) — use `vault-health`.
- For processing new notes into atomic form — use `process-notes`.
- For quick single-note review without the queue system — just `Read` and `Edit` directly.

## Constants

- **QUEUE_SIZE_DAILY**: 5
- **QUEUE_SIZE_WEEKLY**: 10
- **QUEUE_SIZE_MONTHLY**: 15
- **QUEUE_SIZE_SMART**: 10
- **SCORE_CAP**: 20
- **ORPHAN_PENALTY**: 10
- **NEVER_REVIEWED_DAYS**: 365
- **TASK_DIR**: `.mz/task/`

## Core Process

| Phase | Goal                  | Details                    |
| ----- | --------------------- | -------------------------- |
| 0     | Setup                 | Inline below               |
| 1     | Score & Queue         | `phases/score.md`          |
| 1.5   | User approval — queue | Inline below               |
| 2     | Review session        | `phases/review_session.md` |

### Phase 0: Setup

1. Resolve vault path from `$ARGUMENTS`, then `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env. If none resolve, ask the user via AskUserQuestion — never guess.
1. Detect review mode: if `$ARGUMENTS` contains `daily`, `weekly`, or `monthly`, use that mode. Otherwise use `smart`.
1. `task_name` = `<YYYY_MM_DD>_vault-review_<mode>` where `<YYYY_MM_DD>` is today's date (underscores) and `<mode>` is the resolved review mode; on same-day collision append `_v2`, `_v3`.
1. Create `TASK_DIR<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <path>`, `Mode: <mode>`.

### Phase 1.5: User approval — Review Queue

**This orchestrator** (not a subagent) must present the review queue to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/review_queue.md` in full.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `review_queue.md`. Never substitute a template, placeholder list, or status summary — the user must review the actual ranked queue (note titles, scores, maturity, outlinks) in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Review Queue Ready**
Your queue of notes ranked by review due date, orphan status, and maturity. Review the queue below and approve to start the session.

- **Approve** → proceed to Phase 2 (review session)
- **Reject** → mark task as aborted, no notes updated
- **Feedback** → adjust queue size or parameters, regenerate and re-present
```

Then invoke AskUserQuestion with this body (where `<verbatim review_queue.md contents>` is replaced by the bytes you just read):

```
Review queue for today:

<verbatim review_queue.md contents>

MOC gaps detected: <N gaps from moc-gap-detector> — details in .mz/task/<task_name>/moc_gaps.md

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

Response handling:

- **"approve"** → update state to `queue_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Number** (e.g. `5`) → regenerate the queue with that size, re-present **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves.
- **Feedback** → adjust queue parameters (exclude a folder, change weights, filter by maturity), re-run Phase 1 if needed, return to this gate, re-present **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                   | Rebuttal                                                                                                                                                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "I know which notes need review, skip the queue." | "Interest-driven review creates survivorship bias — the notes you remember are already linked; the queue surfaces the orphaned ideas that have never found a connection." |
| "Update `last_reviewed` manually later."          | "Manual timestamp updates are skipped 80% of the time; without accurate `last_reviewed` data the queue degrades into random selection."                                   |
| "Skip the MOC gap detection, just do the review." | "MOC gaps and review needs are correlated — a cluster of seedling notes all lacking a MOC is exactly the pattern vault-review is designed to surface."                    |

## Red Flags

- Starting a review without showing the queue first — a hidden queue means the user cannot redirect.
- Marking notes as reviewed without the user confirming they were actually read.
- Reviewing notes in a fixed order (alphabetical, recency) instead of composite scoring.
- Proceeding to Phase 2 without explicit "approve" from the user.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-review verification:
  [ ] Ranked queue presented via AskUserQuestion before session started
  [ ] `last_reviewed` updated only for notes the user confirmed reviewing
  [ ] MOC gaps surfaced alongside the queue (from moc-gap-detector)
  [ ] state.md Status is `completed` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## Error Handling

- **Vault path missing or invalid** → escalate via AskUserQuestion; never guess a default.
- **Zero permanent notes found** (empty glob) → escalate via AskUserQuestion with the scanned folder path; the vault layout may differ from the default convention.
- **`moc-gap-detector` returns empty or malformed** → retry the dispatch once; if still empty, note the gap in `state.md` and continue the review session without MOC gap data.
- **All notes have identical scores** (degenerate queue) → fall back to recency sort and note the degenerate condition in `state.md`.
