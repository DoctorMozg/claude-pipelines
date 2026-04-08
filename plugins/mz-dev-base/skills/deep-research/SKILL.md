---
name: deep-research
description: ALWAYS invoke when the user wants exhaustive multi-source research on any topic. Triggers: "research X", "deep dive into", "comprehensive analysis of", "what is the state of". Splits the topic into domains, dispatches parallel researcher agents that each scan 20-100 web pages, then synthesizes findings into a comprehensive report. Provide a topic as the argument.
argument-hint: <research topic>
allowed-tools: Agent, Bash, Read, Write
---

# Deep Research

Conduct exhaustive, multi-agent research on a topic by splitting it into domains and running parallel researcher agents.

## Arguments

`$ARGUMENTS` is the research topic or question. If empty, ask the user.

## Process

Steps 2-5 are detailed in `phases/research_and_report.md`. Step 1 (decomposition + approval gate) is inline below.

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

Use AskUserQuestion with:

```
Research decomposition ready. Please review:

<numbered list of subtopics with descriptions>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback
(e.g. "add a subtopic on X", "merge topics 2 and 4", "drop topic 3").
```

**Response handling**:

- **"approve"** → proceed to Step 2 (dispatch researchers).
- **"reject"** → stop. Do not proceed.
- **Feedback** → adjust the decomposition accordingly, then return to this gate and re-present **via AskUserQuestion** using the same format. This is a loop — repeat until the user explicitly approves. Never dispatch researchers without explicit approval.

### 2. Dispatch parallel researcher agents

Launch a `researcher` agent per subtopic in parallel with exhaustive research instructions.

**See `phases/research_and_report.md` → Step 2** for the researcher dispatch prompt template and parallel launch requirements.

### 3. Collect and synthesize

After all agents complete, cross-reference findings, identify emergent patterns, and assess coverage.

**See `phases/research_and_report.md` → Step 3** for the synthesis process.

### 4. Write the report

Write the final report to `.mz/research/` using the naming convention `research_<YYYY_MM_DD>_<slugified_topic>.md`.

**See `phases/research_and_report.md` → Step 4** for the full report template.

### 5. Report to user

Display path, source count, subtopic count, and top 3-5 findings.
