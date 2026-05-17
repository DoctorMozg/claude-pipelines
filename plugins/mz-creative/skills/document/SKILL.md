---
name: document
description: ALWAYS invoke when the user wants to create or polish technical documentation for a project. Triggers: "write docs for", "document this", "polish the README", "create API reference", "write a tutorial for", "draft a how-to". Produces Diátaxis-aligned documentation grounded in codebase research, then runs an automatic naturalize pass.
argument-hint: <what to document or polish>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
model: sonnet
---

# Technical Documentation Pipeline

## Overview

Creates or polishes technical documentation for a project. Researches the codebase first, dispatches `expert-technical-writer` (opus) to write the document, then runs `expert-naturalizer` (opus) to remove residual AI patterns. Output lands at `.mz/reports/<YYYY_MM_DD>_document_<slug>.md`.

## When to Use

- User asks to create docs (README, API reference, guide, tutorial, how-to, explanation)
- User asks to polish or rewrite existing documentation
- Triggers: "write docs for X", "document this module", "draft API reference", "polish the README", "create a tutorial"

### When NOT to use

- User wants promotional or marketing copy — use `copywrite`
- User wants only an AI-text rewrite of existing prose — use `naturalize`
- User wants code review or audit — use `review-branch` or `audit`
- User wants to brainstorm doc structure — use `brainstorm`

## Input

`$ARGUMENTS` — description of what to document. Inline modifiers:

- `scope:branch|global|working` — constrains codebase research to a subset (default: `global`)
- `type:tutorial|howto|reference|explanation|readme|api|all` — Diátaxis content type target (default: `all` lets the writer choose; explicit type produces a single-type doc)
- `@doc:<path>` — existing document to polish instead of creating from scratch

If `$ARGUMENTS` is empty, ask via `AskUserQuestion`. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- **Default**: `global`
- Scope constrains **research only** — Phase 2 writing and Phase 3 naturalization read whatever the writer needs

## Constants

- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`
- **MAX_DOC_TYPES**: 4 (tutorial / how-to / reference / explanation per Diátaxis)

## Core Process

### Phase Overview

| #   | Phase                                | File                 | Loop?             |
| --- | ------------------------------------ | -------------------- | ----------------- |
| 0   | Setup                                | inline below         | —                 |
| 1   | Codebase research                    | `phases/research.md` | —                 |
| 1.5 | Research approval gate               | inline below         | feedback sub-loop |
| 2   | Writing (expert-technical-writer)    | `phases/writing.md`  | —                 |
| 3   | Auto-naturalize (expert-naturalizer) | `phases/writing.md`  | —                 |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. Extract: brief, `scope:`, `type:`, `@doc:` references.
1. If brief is empty → `AskUserQuestion` for the topic. Never guess.
1. `task_name` = `<YYYY_MM_DD>_document_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary (max 20 chars). On same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md`: schema_version: 2, Status, Phase, Started, phase_complete: false, what_remains: [], FilesWritten.
1. Emit a visible setup block: `task_name`, working dir, report path, detected modifiers.

### Phase 1.5: Research Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/research.md` with the Read tool. Capture the full file contents (stack detection, public APIs, conventions, prior art, constraints, proposed doc structure) into context.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `research.md`. Never substitute a path, status summary, or `<contents of research.md>` placeholder — the user must review the actual research artifact in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Research ready for review**
Codebase research complete. Includes detected stack, public APIs, conventions, prior doc art, and the proposed Diátaxis structure for the new document.

- **Approve** → proceed to Phase 2 (writing)
- **Reject** → task marked aborted, no docs written
- **Feedback** → re-run research with your input, loop back here
```

Invoke AskUserQuestion with this body (where `<verbatim research.md contents>` is replaced by the bytes you just read):

```
Research complete. Please review and approve before writing begins:

<verbatim research.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → update state to `research_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-run Phase 1 with feedback, overwrite `research.md`, return to this gate, re-read `research.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                      | Rebuttal                                            |
| ------------------------------------ | --------------------------------------------------- |
| "skip research, just write the docs" | docs without grounding hallucinate API signatures   |
| "skip the approval gate"             | wrong doc structure costs 3× to fix after writing   |
| "skip the naturalize pass"           | tech-writer output still carries AI-pattern residue |

## Red Flags

- You wrote the document inline instead of dispatching `expert-technical-writer`.
- You skipped the research approval gate.
- You skipped the naturalize pass — Phase 3 is mandatory.
- The final document mixes Diátaxis types without explicit section labels.
- You fabricated API signatures the codebase does not contain.

## Verification

Output a visible final block:

```
Documentation pipeline complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_document_<slug>.md
Diátaxis:   <types written, e.g., tutorial+reference>
Naturalize: applied (<words removed>, <patterns broken>)
Files:
  - research.md
  - <output>.md (post-naturalize)
```

If any phase is incomplete, print the blocker explicitly.

## Error Handling

- Empty brief → `AskUserQuestion`. Never guess.
- `@doc:` path does not exist → ask the user whether to proceed without it.
- `scope:` resolves to zero files → escalate via AskUserQuestion; offer to widen scope.
- `expert-technical-writer` returns `BLOCKED` or `NEEDS_CONTEXT` → re-dispatch once with the missing context filled; if still blocked, escalate.
- `expert-naturalizer` returns `BLOCKED` → keep the technical-writer output as the final artifact and warn the user that naturalization did not run.
- Update `state.md` before and after every agent dispatch.

## State Management

Update `.mz/task/<task_name>/state.md` after each phase:

- `Status:` `pending` | `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` `0` | `1` | `1.5` | `2` | `3`
- `FilesWritten:` cumulative list

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

Never rely on conversation memory for cross-phase state.
