---
name: lead-gen
description: ALWAYS invoke when the user wants to find potential companies, generate leads, or plan outreach. Triggers: "find companies", "lead generation", "outreach", "prospect", "find potential clients".
argument-hint: <target description> [sector:filter] [limit:N]
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

## Argument Parsing

Extract from `$ARGUMENTS`:

- **goal** — the full description (everything not matching a parameter pattern)
- **sector** — optional, from `sector:<value>` (default: inferred by strategist)
- **limit** — optional, from `limit:<N>` (default: 20)

## Directory Structure

```
.mz/outreach/<run_name>/
├── state.json
├── strategy.json
├── sources.json
├── _scout/                        # temp: bulk arrays per source (cleaned after dedup)
│   └── <source_slug>.json
├── _enrichment/                   # temp: per-company enrichment parts (cleaned after merge)
│   └── <slug>/
│       ├── contacts.json
│       ├── news.json
│       ├── growth.json
│       └── tech.json
├── companies/                     # permanent: one pair per company
│   ├── <slug>.json                # machine-readable, progressively enriched
│   ├── <slug>.md                  # human-readable dossier card
│   └── ...
├── scout_summary.md
└── outreach_<YYYY_MM_DD>_<goal_slug>.md  # executive summary + scored ranking + card references
```

## Core Process

### Phase Overview

| #   | Phase                     | Agent(s)                              | Details                           |
| --- | ------------------------- | ------------------------------------- | --------------------------------- |
| 0   | Setup                     | —                                     | Inline below                      |
| 1   | Strategy                  | `outreach-strategist`                 | `phases/discovery.md`             |
| 1.5 | User approval of strategy | — (orchestrator, AskUserQuestion)     | `phases/discovery.md` §Phase 1.5  |
| 2   | Source Research           | `outreach-source-researcher`          | `phases/discovery.md`             |
| 3   | Scout + Dedup             | N x `outreach-scout` (parallel)       | `phases/discovery.md`             |
| 4   | Scan                      | N x `outreach-scanner` (parallel)     | `phases/enrichment_and_report.md` |
| 5   | Enrich                    | `outreach-enrichment-orchestrator`    | `phases/enrichment_and_report.md` |
| 6   | Score                     | inline (orchestrator)                 | `phases/enrichment_and_report.md` |
| 7   | Write Cards               | N x `outreach-card-writer` (parallel) | `phases/enrichment_and_report.md` |
| 8   | Report                    | `outreach-reporter`                   | `phases/enrichment_and_report.md` |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

**Phase 1.5** (approval gate): after Phase 1 writes `strategy.json`, the orchestrator presents the strategy to the user via AskUserQuestion before any expensive research/fan-out runs. See `phases/discovery.md` §Phase 1.5 for the gate content, AskUserQuestion prompt, and feedback-loop contract. Never skip this gate or delegate it to a subagent.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 23, not discipline. See Rule 17.

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
