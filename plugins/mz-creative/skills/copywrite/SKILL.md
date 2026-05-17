---
name: copywrite
description: ALWAYS invoke when the user wants promotional, marketing, or persuasive copy. Triggers: "write a landing page for", "draft a launch email", "write release notes", "social post for", "pitch one-pager", "marketing copy for", "announcement copy". Researches positioning + product context, dispatches expert-copywriter, then runs an automatic naturalize pass.
argument-hint: <what to promote, plus format:landing|email|announcement|social|changelog|pitch>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
model: sonnet
---

# Copywriting Pipeline

## Overview

Produces promotional and persuasive copy — landing pages, launch emails, announcements, social posts, changelog entries, and pitch one-pagers. Researches the product and competitive positioning first, dispatches `expert-copywriter` (opus) to write the copy, then runs `expert-naturalizer` (opus) to remove residual AI patterns. Output lands at `.mz/reports/<YYYY_MM_DD>_copywrite_<slug>.md`.

## When to Use

- User wants a landing page, email, announcement, social post, changelog entry, or pitch
- User wants to rewrite existing marketing copy with sharper positioning
- Triggers: "write a landing page", "draft a launch email", "release-notes for X", "social post about Y", "pitch one-pager", "marketing copy for"

### When NOT to use

- User wants technical documentation — use `document` (which also runs naturalize as Phase 3)
- User wants only an AI-text rewrite of existing prose — use `naturalize`
- User wants an internal report or review — use `audit`, `review-branch`, etc.
- User wants to brainstorm positioning before writing — use `brainstorm` first, then `copywrite`

## Input

`$ARGUMENTS` — description of what to promote. Inline modifiers:

- `format:landing|email|announcement|social|changelog|pitch` — the output format. **Required**. If absent, the orchestrator asks via `AskUserQuestion`.
- `scope:branch|global|working` — constrains codebase scan to a subset (default: `global`). Used for tone-matching against existing copy in the repo.
- `@brief:<path>` — existing brief, product spec, or feature doc to ground the copy in. Strongly recommended.

If `$ARGUMENTS` is empty, ask via `AskUserQuestion` for the product, audience, and format. Never guess.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- **Default**: `global`
- Scope constrains **codebase research only** — Phase 2 writing and Phase 3 naturalization read whatever the writer needs

## Constants

- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`
- **SUPPORTED_FORMATS**: `landing`, `email`, `announcement`, `social`, `changelog`, `pitch`

## Core Process

### Phase Overview

| #   | Phase                                  | File                 | Loop?             |
| --- | -------------------------------------- | -------------------- | ----------------- |
| 0   | Setup                                  | inline below         | —                 |
| 1   | Research (positioning + codebase tone) | `phases/research.md` | —                 |
| 1.5 | Brief approval gate                    | inline below         | feedback sub-loop |
| 2   | Writing (expert-copywriter)            | `phases/writing.md`  | —                 |
| 3   | Auto-naturalize (expert-naturalizer)   | `phases/writing.md`  | —                 |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. Extract: topic, `format:`, `scope:`, `@brief:` references.
1. If `format:` is missing → `AskUserQuestion` with the six supported formats as variant options. Never guess.
1. If topic/brief is empty → `AskUserQuestion` for what to promote and to whom. Never guess.
1. If `@brief:<path>` is referenced, read the file and verify it exists and is readable text.
1. `task_name` = `<YYYY_MM_DD>_copywrite_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary derived from the topic + format (max 20 chars). On same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md`: schema_version: 2, Status, Phase, Started, phase_complete: false, what_remains: [], Format, BriefSource, FilesWritten.
1. Emit a visible setup block: `task_name`, format, brief source, scope, report path.

### Phase 1.5: Brief Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/brief.md` with the Read tool. Capture the full file contents (positioning, audience, value claim, named customers/numbers, tone decisions, format-specific constraints) into context.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `brief.md`. Never substitute a path, status summary, or `<contents of brief.md>` placeholder — the user must review the actual brief in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Brief ready for review**
Positioning research complete. Includes audience, value claim, evidence/named users, format constraints, and tone decisions.

- **Approve** → proceed to Phase 2 (writing)
- **Reject** → task marked aborted, no copy written
- **Feedback** → re-run research with your input, loop back here
```

Invoke AskUserQuestion with this body (where `<verbatim brief.md contents>` is replaced by the bytes you just read):

```
Brief ready. Please review and approve before writing begins:

<verbatim brief.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → update state to `brief_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-run Phase 1 with feedback, overwrite `brief.md`, return to this gate, re-read `brief.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                             | Rebuttal                                                                                     |
| ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| "skip research, the brief is enough"        | the brief lacks competitive context and tone-matching against the project's voice            |
| "skip the approval gate to save time"       | bad positioning costs 3× to fix after the copy is written and shared                         |
| "skip the naturalize pass"                  | copywriter output still carries AI-pattern residue (adjective stacks, mechanical antithesis) |
| "format doesn't matter, write generic copy" | a landing page and a changelog are different shapes; generic copy fits neither               |

## Red Flags

- You wrote the copy inline instead of dispatching `expert-copywriter`.
- You skipped the brief approval gate.
- You skipped the naturalize pass — Phase 3 is mandatory.
- You invented metrics, customer names, or capabilities not in the brief.
- The final copy uses the wrong format (e.g., five-paragraph essay structure on a social post).

## Verification

Output a visible final block:

```
Copywriting pipeline complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_copywrite_<slug>.md
Format:     <landing|email|announcement|social|changelog|pitch>
Naturalize: applied (<words removed>, <patterns broken>)
Files:
  - brief.md
  - <output>.md (post-naturalize)
```

If any phase is incomplete, print the blocker explicitly.

## Error Handling

- Empty topic → `AskUserQuestion`. Never guess.
- Missing `format:` → `AskUserQuestion` with the six supported formats. Never guess.
- `@brief:` path does not exist → ask the user whether to proceed without it; warn that copy quality drops sharply without a grounded brief.
- `scope:` resolves to zero files → continue with empty codebase tone-match; warn the user that voice-matching is unavailable.
- `expert-copywriter` returns `BLOCKED` or `NEEDS_CONTEXT` → re-dispatch once with the missing context filled; if still blocked, escalate via AskUserQuestion.
- `expert-naturalizer` returns `BLOCKED` → keep the copywriter output as the final artifact and warn the user that naturalization did not run.
- Update `state.md` before and after every agent dispatch.

## State Management

Update `.mz/task/<task_name>/state.md` after each phase:

- `Status:` `pending` | `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` `0` | `1` | `1.5` | `2` | `3`
- `Format:` `landing` | `email` | `announcement` | `social` | `changelog` | `pitch`
- `BriefSource:` `inline` | `file:<path>` | `none`
- `FilesWritten:` cumulative list

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

Never rely on conversation memory for cross-phase state.
