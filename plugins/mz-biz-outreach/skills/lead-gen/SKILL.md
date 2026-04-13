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

Use `.mz/outreach/<run_name>/` with `state.json`, `strategy.json`, `sources.json`, temp `_scout/` and `_enrichment/` folders, permanent `companies/<slug>.json` + `companies/<slug>.md` pairs, `scout_summary.md`, and `outreach_<YYYY_MM_DD>_<goal_slug>.md`.

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

Present: the approved target profile, sector/geo scope, candidate-source plan, and estimated fan-out cost from `strategy.json` — the user confirms scope before any expensive research runs. See `phases/discovery.md` §Phase 1.5 for extended presentation details.

Use AskUserQuestion with:

```
Strategy drafted for "<goal>". Target profile, sector filters, and candidate sources are in .mz/outreach/<run_name>/strategy.json.

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update `state.json` phase to `strategy_approved`, proceed to Phase 2.
- **"reject"** → update `state.json` to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-dispatch `outreach-strategist` with the feedback appended, overwrite `strategy.json`, return to this gate, re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves. Never proceed without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 17, not discipline. See Rule 17.

## Red Flags

- You dispatched enrichment before the user approved the target profile.
- You used a banned data source (scraped LinkedIn, unverified aggregators, AI-summarized listings).
- Report lives in chat instead of `.mz/reports/` or the run's executive summary file.

## Verification

Before completing, output a visible block showing: run name, company count after dedup, scored leads count, and the absolute path of the executive summary report. Confirm the report file and per-company card pairs exist on disk.

______________________________________________________________________

## Phase 0: Setup

Parse arguments. Derive run name: short snake_case + today's date, max 30 chars.
Example: `"find DevOps clients in DACH"` → `devops_dach_2026-04-06`

```bash
mkdir -p .mz/outreach/<run_name>/companies
```

Write `state.json`:

```json
{
  "goal": "<goal>",
  "sector": "<parsed or null>",
  "limit": 20,
  "run_name": "<run_name>",
  "phase": "setup",
  "started_at": "<ISO>"
}
```

After setup completes, read `phases/discovery.md` and proceed to Phase 1.

______________________________________________________________________

## Resume Support

Before creating anything in Phase 0, check if `state.json` exists. If it does, read `phase` and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent fails or returns empty: log in `state.json` under `"errors": []`, continue with available data
- ALL agents in a phase fail (zero results): stop the pipeline and report the failure
- Never fabricate data — incomplete results are better than false results
- Corrupted company JSON during any phase: log the error, skip that company, continue
