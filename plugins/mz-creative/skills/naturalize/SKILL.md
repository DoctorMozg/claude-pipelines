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
1. Write `state.md`: Status, Phase, Started, InputSource, ResearchRequested, FilesWritten.
1. Emit a visible setup block: `task_name`, input source, length in words, research flag.

### Phase 1.5: Analysis Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/analysis.md` with the Read tool. Capture the full file contents (detected patterns, severity, sentence-rhythm metrics, proposed rewriting strategy) into context.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `analysis.md`. Never substitute a path, status summary, or `<contents>` placeholder — the user must review the actual analysis in the question itself, not have to open the file separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Analysis ready for review**
AI pattern detection complete. Includes detected vocabulary spikes, structural patterns, sentence-rhythm metrics, and the proposed rewriting strategy.

- **Approve** → proceed to Phase 2 (rewriting)
- **Reject** → task marked aborted, no rewrite performed
- **Feedback** → adjust the rewriting strategy per your input, loop back here
```

Invoke AskUserQuestion with this body (where `<verbatim analysis.md contents>` is replaced by the bytes you just read):

```
Pattern analysis complete. Please review and approve the rewriting strategy:

<verbatim analysis.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → update state to `analysis_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust the rewriting strategy per feedback, overwrite `analysis.md`, return to this gate, re-read `analysis.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

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

Never rely on conversation memory for cross-phase state.
