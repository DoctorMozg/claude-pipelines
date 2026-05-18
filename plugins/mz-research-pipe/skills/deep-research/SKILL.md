---
name: deep-research
description: ALWAYS invoke when the user wants exhaustive multi-source research on any topic. Triggers:"research X","deep dive into","comprehensive analysis of","what is the state of". Provide a topic as the argument.
argument-hint: <research topic>
model: sonnet
allowed-tools: Agent, Bash, Read, Write
---

# Deep Research

## Overview

Conduct exhaustive, multi-agent research on a topic by decomposing it into independent domains, dispatching parallel pipeline-web-researcher agents, and synthesizing findings into a single report under `.mz/research/`.

## When to Use

Triggers: "research X", "deep dive into", "comprehensive analysis of", "what is the state of".

### When NOT to use

- The user wants a one-line factual answer — use plain web search.
- The topic is narrow enough for a single pipeline-web-researcher agent — dispatch directly.
- The user wants a code review or audit — use `review-branch` or `audit`.

## Arguments

`$ARGUMENTS` is the research topic or question. If empty, ask the user.

## Core Process

### Phase Overview

| #   | Phase                         | Details                         |
| --- | ----------------------------- | ------------------------------- |
| 0   | Setup                         | inline below                    |
| 1   | Decomposition + approval gate | inline below                    |
| 2-5 | Research, synthesis, report   | `phases/research_and_report.md` |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. If the research topic is empty, escalate via AskUserQuestion — never guess.
1. `task_name` = `<YYYY_MM_DD>_deep_research_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<slug>` is a snake_case summary of the topic (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with, in order: `schema_version: 2` (first line), `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `phase_complete: false`, `what_remains: []`, `Topic: <original argument>`, `Subtopics: []`.
1. Emit a visible setup block: `task_name`, topic, working dir, report dir (`.mz/research/`).

### 1. Analyze and decompose the topic

Break `$ARGUMENTS` into 3-7 independent research domains/subtopics. Each subtopic should be:

- Researchable independently (no dependency on other subtopics' results)
- Specific enough to yield focused search results
- Broad enough to warrant 20+ pages of research

Example for "State of WebAssembly in 2026":

- **Runtime performance** — benchmarks, comparison with native code, recent improvements
- **Language support** — which languages compile to WASM, toolchain maturity
- **Browser adoption** — browser support, feature parity, market share
- **Server-side WASM** — WASI, edge computing, cloud runtimes
- **Ecosystem** — package managers, frameworks, developer tools
- **Production usage** — companies using WASM in production, case studies

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-write + capture**: Write the decomposition to `.mz/task/<task_name>/decomposition.md` as a numbered list of 3-7 subtopics, each with a 1-3 sentence description and rationale. Then Read that file with the Read tool to capture its full contents into context for the gate.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a normal markdown chat message. Emit the full verbatim contents of `.mz/task/<task_name>/decomposition.md` — do not substitute a path, summary, or placeholder:

```
## Research decomposition ready for review — deep-research

<verbatim contents of .mz/task/<task_name>/decomposition.md>

---
**Approve** → proceed to parallel dispatch of pipeline-web-researcher agents across all subtopics  ·  **Reject** → abort the task, mark state aborted_by_user  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the decomposition in the question body:

- question: `The research decomposition above is ready for review.`
- options: **Approve** — proceed to parallel dispatch of pipeline-web-researcher agents · **Reject** — abort the task, mark state aborted_by_user

**Response handling**:

- **Approve** → proceed to Step 2 (dispatch researchers).
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → adjust the decomposition accordingly, overwrite `decomposition.md`, return to this gate, re-read `decomposition.md`, and re-emit the entire plan message from scratch with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval; never dispatch researchers without explicit approval.

### 2. Dispatch parallel pipeline-web-researcher agents

Launch a `pipeline-web-researcher` agent per subtopic in parallel. **See `phases/research_and_report.md` → Step 2** for the dispatch prompt template.

### 3. Collect and synthesize

After all agents complete, cross-reference findings, identify emergent patterns, and assess coverage. **See `phases/research_and_report.md` → Step 3**.

### 4. Write the report

Write the final report to `.mz/research/` using the naming convention `<YYYY_MM_DD>_research_<slugified_topic>.md`. **See `phases/research_and_report.md` → Step 4** for the template.

### 5. Report to user

Display path, source count, subtopic count, and top 3-5 findings.

## Techniques

Techniques: delegated to phase files — see `phases/research_and_report.md`.

## Common Rationalizations

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You dispatched a single researcher instead of a parallel fan-out across subtopics.
- You skipped the decomposition approval gate and jumped straight to research.
- The report lives in chat output instead of `.mz/research/<file>.md`.

## Verification

Output the final report path (`.mz/research/<YYYY_MM_DD>_research_<slug>.md`), confirm the file exists on disk, and print the number of subtopics researched alongside the top 3-5 findings.

## Error Handling

- **Empty topic argument** → escalate via AskUserQuestion; never guess.
- **Missing tooling** (`WebSearch`/`WebFetch` unavailable, `Agent` tool absent) → escalate via AskUserQuestion rather than degrade silently.
- **Empty researcher result** (agent returns nothing or malformed output) → retry that subtopic once with a clarified prompt; if still empty, note the gap in `state.md` and escalate via AskUserQuestion before writing the final report.
- Never guess — on any ambiguity (unclear scope, conflicting subtopics, source availability) escalate via AskUserQuestion rather than fabricate.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.
