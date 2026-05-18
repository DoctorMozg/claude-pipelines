---
name: naturalize
description: ALWAYS invoke when the user wants to rewrite AI-generated text to sound human. Triggers: "humanize this text", "make this sound less like AI", "rewrite to be more natural", "remove AI patterns from", "naturalize this prose", "de-AI this draft". Detects AI patterns first, gets user approval, then rewrites via the expert-naturalizer agent.
argument-hint: <text or @file:path to rewrite>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
model: sonnet
---

# Text Naturalization Pipeline

## Overview

Rewrites AI-generated text to read as if a human wrote it. Detects AI patterns first (vocabulary spikes, structural templates, sentence-rhythm uniformity, em-dash overuse, etc.), presents findings for user approval, then dispatches `expert-naturalizer` (opus) to rewrite. Optional web research pass to refresh pattern data before analysis.

## When to Use

- User has AI-generated prose and wants it rewritten to sound human
- User wants to detect AI patterns in a document before rewriting
- Triggers: "humanize this", "make this sound less like AI", "remove AI patterns from", "rewrite to be natural"

### When NOT to use

- User wants original technical documentation written from scratch — use `document` (which already runs naturalize as Phase 3)
- User wants promotional copy — use `copywrite` (which also naturalizes)
- User wants to fix grammar in human-written text — this skill assumes AI patterns are present and may damage natural prose
- User wants to translate text — use `translate`

## Input

`$ARGUMENTS` — the text to rewrite or a file reference. Forms accepted:

- Inline text following the skill invocation (the entire arg block becomes the input)
- `@file:<path>` — read text from the specified file
- `research:yes` — pull current AI pattern data from authoritative web sources before analysis (use when the embedded vocabulary may be 18+ months old)

If `$ARGUMENTS` is empty, ask via `AskUserQuestion` for either inline text or a file path. Never guess.

## Constants

- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`
- **CHUNK_THRESHOLD**: 2000 (words above this trigger section-by-section rewriting)
- **MAX_PATTERNS_REPORTED**: 30 (top patterns shown in approval gate)

## Core Process

### Phase Overview

| #   | Phase                                      | File                  | Loop?             |
| --- | ------------------------------------------ | --------------------- | ----------------- |
| 0   | Setup                                      | inline below          | —                 |
| 1   | Pattern analysis (+ optional web research) | `phases/analysis.md`  | —                 |
| 1.5 | Analysis approval gate                     | inline below          | feedback sub-loop |
| 2   | Rewriting (expert-naturalizer)             | `phases/rewriting.md` | —                 |
| 2.5 | Optional in-place file update gate         | `phases/rewriting.md` | —                 |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. Detect: inline text vs `@file:` reference, presence of `research:yes`.
1. If empty → `AskUserQuestion` for input source. Never guess.
1. If `@file:` referenced, read the file and verify it is text (not binary, not too large to fit in context — if >50KB, warn the user).
1. `task_name` = `<YYYY_MM_DD>_naturalize_<slug>` where slug derives from the input (file basename or first 5 words of inline text). On collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write the input text to `.mz/task/<task_name>/input.md` for reference.
1. Write `state.md`: schema_version: 2, Status, Phase, Started, phase_complete: false, what_remains: [], InputSource, ResearchRequested, FilesWritten.
1. Emit a visible setup block: `task_name`, input source, length in words, research flag.

### Phase 1.5: Analysis Approval Gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/analysis.md` and capture the full contents (detected patterns, severity, sentence-rhythm metrics, proposed rewriting strategy) into context.

**Surface 1 — emit the plan message.** Output the full verbatim contents of `.mz/task/<task_name>/analysis.md` as a normal markdown chat message. Emit the full verbatim contents — do not substitute a path, summary, or placeholder. Structure:

```
## Analysis ready for review — naturalize

<verbatim contents of .mz/task/<task_name>/analysis.md>

---
**Approve** → proceed to Phase 2 (rewriting)  ·  **Reject** → task marked aborted, no rewrite performed  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** After the plan message, call AskUserQuestion. The question must NOT re-embed the analysis — it lives in the plan message above.

- question: `The analysis above is ready for review.`
- options: **Approve** — proceed to Phase 2 (rewriting) · **Reject** — abort task, no rewrite performed

**Response handling**:

- **Approve** → update state to `analysis_approved`, proceed to Phase 2.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → adjust the rewriting strategy per feedback, overwrite `analysis.md`, return to Surface 1, re-read `analysis.md`, and re-emit the entire plan message from scratch with the full new contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                       | Rebuttal                                                                              |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------- |
| "the text looks fine, skip analysis"                  | structural AI patterns are invisible without checking; vocabulary alone is not enough |
| "skip the approval gate to save time"                 | the user may want to preserve technical terms the agent would otherwise replace       |
| "skip web research, the embedded list is good enough" | AI vocabulary shifts every 18 months; `research:yes` exists for a reason              |

## Red Flags

- You rewrote the text inline without dispatching `expert-naturalizer`.
- You skipped the analysis approval gate.
- You over-edited a code block, table, or proper name.
- You added a citation, statistic, or named source that wasn't in the input.
- You "improved" text that was already human-written.

## Verification

Output a visible final block:

```
Naturalization complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_naturalize_<slug>.md
Input:      <source> (<words>)
Output:     <words> (delta: <±N>%)
Patterns:   <count broken>
Burstiness: <before> → <after>
File update: <yes|no|n/a>
```

If any phase is incomplete, print the blocker explicitly.

## Error Handling

- Empty input → `AskUserQuestion`. Never guess.
- `@file:` path does not exist → escalate via AskUserQuestion; offer alternatives.
- Input is binary or non-text → reject with explanation.
- Input >50KB → warn user and ask whether to proceed (long inputs may exceed context).
- `expert-naturalizer` returns `BLOCKED` → preserve original text, escalate.
- `expert-naturalizer` returns `NEEDS_CONTEXT` → fill the missing context (e.g., preserve list), re-dispatch.
- Update `state.md` before and after every agent dispatch.

## State Management

Update `.mz/task/<task_name>/state.md` after each phase:

- `Status:` `pending` | `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` `0` | `1` | `1.5` | `2` | `2.5`
- `InputSource:` `inline` | `file:<path>`
- `ResearchRequested:` `yes` | `no`
- `FilesWritten:` cumulative list
- `FileUpdateApplied:` `yes` | `no` | `n/a` (only relevant when `@file:` was used)

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

Never rely on conversation memory for cross-phase state.
