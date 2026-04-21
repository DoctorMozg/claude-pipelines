---
name: lead-gen
description: ALWAYS invoke when the user wants to find potential companies, generate leads, or plan outreach. Triggers: "find companies", "lead generation", "outreach", "prospect", "find potential clients".
argument-hint: <target description> [sector:filter] [limit:N]
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, WebFetch, WebSearch
---

# Lead Generation Pipeline

## Overview

You are an orchestrator that drives a full business outreach intelligence pipeline. You receive an outreach goal and autonomously define strategy, research sources, discover companies, scan reputations, enrich with deep intelligence, score leads, write per-company dossier cards, and produce an executive summary report. Every company gets exactly two permanent files: a `.json` (machine-readable, progressively enriched) and a `.md` (human-readable dossier card). No bulk JSON arrays.

## When to Use

Invoke when the user wants to find prospective companies, build a lead list, or prepare outreach research. Trigger phrases: "find companies", "lead generation", "outreach", "prospect", "find potential clients".

### When NOT to use

- The user wants to draft outreach copy or messages — this skill researches targets, not content.
- The user wants competitive analysis of a single named company — use `explain` or `investigate` on public sources instead.
- The user has not defined an outreach goal or target profile — ask before invoking.

## Input

- `$ARGUMENTS` — The outreach goal. Examples:
  - `"find potential clients for our DevOps consulting in DACH region"`
  - `"SaaS companies in Latin America sector:HR-tech limit:30"`
  - `"find AI startups in Singapore for partnership opportunities"`

If empty, ask the user what kind of companies they want to find and why.

## Scope Parameter

Extract scope modifiers from `$ARGUMENTS`, case-insensitive. `lead-gen` is outbound (company discovery), so scope controls **which prospective companies enter the funnel**, not which files to scan. Remaining text controls the outreach goal (orthogonal).

- **`sector:<value>`** — restrict discovery to a specific industry/vertical (e.g. `sector:HR-tech`, `sector:fintech`). Default: inferred by `outreach-strategist` from the goal text.
- **`region:<value>`** — restrict discovery to a geographic market (e.g. `region:DACH`, `region:LATAM`). Default: inferred from the goal text; global if no signal.
- **`limit:<N>`** — maximum companies to carry through the pipeline. Default: 20.
- **Default** — full-scope strategist-driven discovery using only the goal text when no modifiers are present.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **goal** — the full description (everything not matching a parameter pattern)
- **sector** — optional, from `sector:<value>` (default: inferred by strategist)
- **region** — optional, from `region:<value>` (default: inferred from goal text)
- **limit** — optional, from `limit:<N>` (default: 20)

## Directory Structure

Two separate directories are used:

- **State** — `.mz/task/<task_name>/state.md`. This is the source of truth across phases; never rely on conversation memory.
- **Outreach data** — `.mz/outreach/<run_name>/` holds `strategy.json`, `sources.json`, temp `_scout/` and `_enrichment/` folders, permanent `companies/<slug>.json` + `companies/<slug>.md` pairs, `scout_summary.md`, and `<YYYY_MM_DD>_outreach_<goal_slug>.md`.

`task_name` follows the pattern `<YYYY_MM_DD>_lead_gen_<slug>`; `run_name` is `<YYYY_MM_DD>_lead_gen_<goal_slug>` (same leading-date convention). They are independent: `task_name` identifies the pipeline invocation, `run_name` identifies the outreach output bundle.

## Core Process

### Phase Overview

| #   | Phase                     | Agent(s)                              | Details                                                       |
| --- | ------------------------- | ------------------------------------- | ------------------------------------------------------------- |
| 0   | Setup                     | —                                     | Inline below                                                  |
| 1   | Strategy                  | `outreach-strategist`                 | `phases/discovery.md`                                         |
| 1.5 | User approval of strategy | — (orchestrator, AskUserQuestion)     | Inline below (+ `phases/discovery.md` §Phase 1.5 for details) |
| 2   | Source Research           | `outreach-source-researcher`          | `phases/discovery.md`                                         |
| 3   | Scout + Dedup             | N x `outreach-scout` (parallel)       | `phases/discovery.md`                                         |
| 4   | Scan                      | N x `outreach-scanner` (parallel)     | `phases/enrichment_and_report.md`                             |
| 5   | Enrich                    | `outreach-enrichment-orchestrator`    | `phases/enrichment_and_report.md`                             |
| 6   | Score                     | inline (orchestrator)                 | `phases/enrichment_and_report.md`                             |
| 7   | Write Cards               | N x `outreach-card-writer` (parallel) | `phases/enrichment_and_report.md`                             |
| 8   | Report                    | `outreach-reporter`                   | `phases/enrichment_and_report.md`                             |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

### Phase 1.5: User Approval of Strategy

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/outreach/<run_name>/strategy.json` with the Read tool. Capture the full file contents (target profile, sector/geo scope, candidate-source plan, estimated fan-out cost) into context. The strategy file is JSON — present it verbatim inside a fenced \`\`\`json block so structure is preserved. See `phases/discovery.md` §Phase 1.5 for the strategy.json schema.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `strategy.json` inside a fenced \`\`\`json block. Never substitute a path, target-profile summary, or one-line description — the user must review the actual strategy fields in the question itself, not have to open the file separately. The user confirms scope before any expensive research runs.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Strategy ready for review**
Target profile, sector, region, and discovery plan drafted. Please review for feasibility before expensive research dispatch.

- **Approve** → proceed to Phase 2 (source research and company discovery)
- **Reject** → task marked aborted, no outreach data generated
- **Feedback** → re-run strategy with your input, loop back here for re-review
```

Invoke AskUserQuestion with this body (where `<verbatim strategy.json contents>` is replaced by the bytes you just read):

````
Strategy drafted for "<goal>". Please review before discovery dispatch:

```json
<verbatim strategy.json contents>
```

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
````

**Response handling**:

- **"approve"** → update `.mz/task/<task_name>/state.md` phase to `strategy_approved`, proceed to Phase 2.
- **"reject"** → update `.mz/task/<task_name>/state.md` Status to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-dispatch `outreach-strategist` with the feedback appended, overwrite `strategy.json`, return to this gate, re-read `strategy.json`, and re-present **via AskUserQuestion** with the full new contents inside the fenced json block — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You dispatched enrichment before the user approved the target profile.
- You used a banned data source (scraped LinkedIn, unverified aggregators, AI-summarized listings).
- Report lives in chat instead of `.mz/reports/` or the run's executive summary file.

## Verification

Before completing, output a visible block showing: run name, company count after dedup, scored leads count, and the absolute path of the executive summary report. Confirm the report file and per-company card pairs exist on disk.

______________________________________________________________________

## Phase 0: Setup

Parse arguments. Derive two names:

- `task_name` (state dir) = `<YYYY_MM_DD>_lead_gen_<slug>` where `<slug>` is a snake_case summary of the goal (max 20 chars) and `<YYYY_MM_DD>` is today's date with underscores.
- `run_name` (outreach output dir) = `<YYYY_MM_DD>_lead_gen_<goal_slug>`, max 30 chars total (keep `<goal_slug>` short to fit). Example: `"find DevOps clients in DACH"` → `2026_04_06_lead_gen_devops_dach`.

```bash
mkdir -p .mz/task/<task_name>
mkdir -p .mz/outreach/<run_name>/companies
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Lead Gen State
- **Status**: running
- **Phase**: 0
- **Started**: <ISO timestamp>
- **Goal**: <goal>
- **Sector**: <parsed or null>
- **Limit**: 20
- **RunName**: <run_name> (outreach output dir)
```

After setup completes, read `phases/discovery.md` and proceed to Phase 1.

______________________________________________________________________

## Resume Support

Before creating anything in Phase 0, check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` field and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent fails or returns empty: append an `Errors:` bullet in `.mz/task/<task_name>/state.md`, continue with available data.
- ALL agents in a phase fail (zero results): stop the pipeline and report the failure.
- Never fabricate data — incomplete results are better than false results.
- Corrupted company JSON during any phase: log the error in state.md, skip that company, continue.
