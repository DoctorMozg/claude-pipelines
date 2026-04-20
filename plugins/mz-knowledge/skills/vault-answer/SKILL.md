---
name: vault-answer
description: 'ALWAYS invoke when asking a question that should be answered from vault notes with inline wikilink citations. Triggers: what does my vault say about, answer from notes, search my vault for, grounded answer.'
argument-hint: <question>
model: sonnet
allowed-tools: Agent, Read, Grep, Glob, Write, AskUserQuestion
---

# Vault Answer

## Overview

Discipline skill for grounded Q&A over vault notes. Dispatches `vault-query-answerer` to produce an answer with inline `[[wikilink]]` citations plus an explicit `## Unknowns` list (claims the vault could not support). Read-only on the vault — writes nothing outside `.mz/task/<task_name>/`. Discipline type because the skill enforces strict citation-grounding rules; the agent must resist the shortcut of answering from general LLM knowledge.

## When to Use

Factual questions that should be answered from vault content — "what does my vault say about X", "search my notes for Y", "summarize what I've written on Z". Trigger phrases: "answer from notes", "grounded answer", "vault-based answer".

### When NOT to use

- Editing notes — use `Edit` directly.
- Finding links between notes — use `vault-connect`.
- General LLM questions not tied to vault content — answer directly without this skill.
- Frontmatter/schema questions — use `vault-schema`.

## Arguments

`$ARGUMENTS` is the question. If empty, escalate via AskUserQuestion — never guess the question.

## Constants

- **TASK_DIR**: `.mz/task/`
- **MAX_NOTES_READ**: 20 — hard cap on notes the answerer may read.
- **MAX_PREVIEW_WORDS**: 300 — per-note preview slice for the answerer.
- **CITATION_DENSITY_MIN_RATIO**: 0.02 — at least 1 `[[wikilink]]` per 50 words of answer prose.

## Core Process

| Phase | Goal                | Details                           |
| ----- | ------------------- | --------------------------------- |
| 0     | Setup               | Inline below                      |
| 1     | Search + synthesize | `phases/search_and_synthesize.md` |

No approval gate — read-only skill, no vault writes.

### Phase 0: Setup

1. Capture `$ARGUMENTS` as the question. If empty, AskUserQuestion for the question — never guess.
1. Resolve vault path from `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env, then walk up from the working directory until a `.obsidian/` folder is found. If nothing resolves, escalate via AskUserQuestion.
1. Derive `task_name = <YYYY_MM_DD>_vault-answer_<question-slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<question-slug>` is a snake_case summary of the question (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. Create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <path>`, `Question: <verbatim>`.

## Common Rationalizations

| Rationalization                                                                  | Rebuttal                                                                                                                                                                                                                 |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Answer from general LLM knowledge when the vault is thin."                      | "This skill exists to surface what the vault knows; general knowledge belongs elsewhere. Thin vault = long `## Unknowns` section — surfacing the gap is the correct behavior, not compensating from general knowledge."  |
| "Skip the `## Unknowns` section if every claim looks grounded."                  | "The `## Unknowns` section is always present; an empty list is still informative — it signals the vault fully covered the question. Omitting the section removes a load-bearing signal from the answer."                 |
| "Invent a plausible-sounding `[[wikilink]]` to hit the citation density target." | "Every `[[wikilink]]` must resolve to a note that was actually read. Invented links corrupt the citation trail silently and make the answer unauditable. Prefer low density with honest citations over fabricated ones." |

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Red Flags

Red Flags: delegated to phase files — see Phase Overview table above.

## Verification

Verification: delegated to phase files — see Phase Overview table above.
