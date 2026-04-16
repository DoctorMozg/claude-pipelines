---
name: deep-research
description: ALWAYS invoke when the user wants exhaustive multi-source research on any topic. Triggers:"research X","deep dive into","comprehensive analysis of","what is the state of". Provide a topic as the argument.
argument-hint: <research topic>
model: sonnet
allowed-tools: Agent, Bash, Read, Write
---

# Deep Research

## Overview

Conduct exhaustive, multi-agent research on a topic by decomposing it into independent domains, dispatching parallel domain-researcher agents, and synthesizing findings into a single report under `.mz/research/`.

## When to Use

Triggers: "research X", "deep dive into", "comprehensive analysis of", "what is the state of".

### When NOT to use

- The user wants a one-line factual answer — use plain web search.
- The topic is narrow enough for a single domain-researcher agent — dispatch directly.
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
1. `task_name` = `deep_research_<slug>_<HHMMSS>` where `<slug>` is a snake_case summary of the topic (max 20 chars) and `<HHMMSS>` is wall-clock time.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Topic: <original argument>`, `Subtopics: []`.
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

**This orchestrator** (not a subagent) must present the decomposition to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-write + capture**: Write the decomposition to `.mz/task/<task_name>/decomposition.md` as a numbered list of 3-7 subtopics, each with a 1-3 sentence description and rationale. Then Read that file with the Read tool to capture its full contents into context for the gate.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `decomposition.md`. Never substitute a path, status summary, count, or `<numbered list of subtopics with descriptions>` placeholder — the user must review the actual decomposition in the question itself, not have to open the file separately.

Invoke AskUserQuestion with this body (where `<verbatim decomposition.md contents>` is replaced by the bytes you just read):

```
Research decomposition ready. Please review:

<verbatim decomposition.md contents>

Feedback examples: add a subtopic, merge two topics, or drop one.

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → proceed to Step 2 (dispatch researchers).
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust the decomposition accordingly, overwrite `decomposition.md`, return to this gate, re-read `decomposition.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval; never dispatch researchers without explicit approval.

### 2. Dispatch parallel domain-researcher agents

Launch a `domain-researcher` agent per subtopic in parallel. **See `phases/research_and_report.md` → Step 2** for the dispatch prompt template.

### 3. Collect and synthesize

After all agents complete, cross-reference findings, identify emergent patterns, and assess coverage. **See `phases/research_and_report.md` → Step 3**.

### 4. Write the report

Write the final report to `.mz/research/` using the naming convention `research_<YYYY_MM_DD>_<slugified_topic>.md`. **See `phases/research_and_report.md` → Step 4** for the template.

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

Output the final report path (`.mz/research/research_<YYYY_MM_DD>_<slug>.md`), confirm the file exists on disk, and print the number of subtopics researched alongside the top 3-5 findings.

## Error Handling

- **Empty topic argument** → escalate via AskUserQuestion; never guess.
- **Missing tooling** (`WebSearch`/`WebFetch` unavailable, `Agent` tool absent) → escalate via AskUserQuestion rather than degrade silently.
- **Empty researcher result** (agent returns nothing or malformed output) → retry that subtopic once with a clarified prompt; if still empty, note the gap in `state.md` and escalate via AskUserQuestion before writing the final report.
- Never guess — on any ambiguity (unclear scope, conflicting subtopics, source availability) escalate via AskUserQuestion rather than fabricate.
