---
name: lead-pipeline
description: Full autonomous outreach pipeline — analyzes goal, discovers sources, scouts companies, scans reviews, enriches with contacts/news/growth/tech data, produces intelligence report. Provide a target description as the argument.
argument-hint: <target description> [sector:filter] [limit:N]
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, WebFetch, WebSearch
---

# Lead Generation Pipeline

You are an orchestrator that drives a full business outreach intelligence pipeline using specialized sub-agents. You receive an outreach goal and autonomously define strategy, research sources, discover companies, scan reputations, enrich with deep intelligence, and produce a scored outreach report.

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
- **limit** — optional, from `limit:<N>` (default: 20 — how many companies to enrich and include in the final report)

## Constants

- **BATCH_SIZE_SCAN**: 5 — companies per scanner agent
- **RUN_DIR**: `.mz/outreach/<run_name>/` — all artifacts saved here

## Phase Overview

1. **Phase 0 — Setup**: Parse arguments, create run directory, write initial state
1. **Phase 1 — Strategy**: `outreach-strategist` defines target profile, scoring criteria, outreach angles
1. **Phase 2 — Source Research**: `outreach-source-researcher` finds best directories for the target
1. **Phase 3 — Scout**: One `outreach-scout` per source (all parallel) → merge and deduplicate
1. **Phase 4 — Scan**: `outreach-scanner` in batches of 5 (all parallel) → merge and sort by score
1. **Phase 5 — Enrich**: `outreach-enrichment-orchestrator` handles all companies, internally dispatching `contact-finder`, `news-finder`, `growth-analyst`, `tech-analyst` per company (4 parallel per company)
1. **Phase 6 — Report**: `outreach-reporter` synthesizes everything into scored report

Each phase reads the previous phase's output files and writes its own. The skill orchestrator only dispatches top-level agents and manages state — it never accumulates company data in its own context.

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse arguments

Extract goal, sector, and limit from `$ARGUMENTS`.

### 0.2 Derive run name

From the goal, derive a short snake_case name (max 30 chars) with today's date.
Example: "find DevOps clients in DACH" -> `devops_dach_2026-04-05`

### 0.3 Create run directory

```bash
mkdir -p .mz/outreach/<run_name>
```

### 0.4 Write initial state

Write `.mz/outreach/<run_name>/state.json`:

```json
{
  "goal": "<original goal>",
  "sector": "<parsed sector or null>",
  "limit": 20,
  "run_name": "<run_name>",
  "phase": "setup",
  "started_at": "<ISO timestamp>"
}
```

______________________________________________________________________

## Phase 1: Strategy

Spawn a single `outreach-strategist` agent:

```
Analyze this outreach goal and define the search strategy:

Goal: "<goal>"
Sector hint: <sector or "not specified">

Write your strategy to: .mz/outreach/<run_name>/strategy.json
```

After the agent completes:

1. Read `.mz/outreach/<run_name>/strategy.json`
1. Extract target profile, search signals, scoring weights, outreach angles, and source hints
1. These will be passed to downstream agents as context
1. Update state.json: `"phase": "strategy_complete"`

______________________________________________________________________

## Phase 2: Research Sources

Spawn a single `outreach-source-researcher` agent:

```
Research the best business directories and data sources for finding companies
matching this target profile:

Target: <target_profile from strategy>
Sectors: <sectors from strategy>
Geography: <geography from strategy>
Source hints from strategist: <source_hints from strategy>

Write your results to: .mz/outreach/<run_name>/sources.json
```

After the agent completes:

1. Read `.mz/outreach/<run_name>/sources.json`
1. Validate it contains at least 1 source
1. If empty, log error to state.json and report: "No sources found. Try broadening the goal."
1. Update state.json: `"phase": "sources_complete", "sources_found": N`

______________________________________________________________________

## Phase 3: Scout

Spawn **one `outreach-scout` agent per source**, all in a single parallel message.

For each source, the prompt is:

```
Scout companies from this data source:

Source: <source name>
URL: <source url>
Type: <source type>
Access notes: <access notes>

Target profile: <target_profile from strategy>
Sector filter: <sectors from strategy>
Count limit: <total limit / number of sources, rounded up, minimum 10>

Write your results to: .mz/outreach/<run_name>/scout_<slugified_source_name>.json
```

After ALL scouts complete:

1. Read all `scout_*.json` files from the run directory
1. Merge into a single array
1. Deduplicate by domain: if the same domain appears from multiple sources, keep the entry with the most non-null fields, merge `source` into a comma-separated list
1. Write merged list to `.mz/outreach/<run_name>/companies_raw.json`
1. Write summary to `.mz/outreach/<run_name>/scout_summary.md`:
   - Total companies found (before and after dedup)
   - Per-source breakdown
   - First 20 company names as preview
1. Update state.json: `"phase": "scout_complete", "companies_found": N`

______________________________________________________________________

## Phase 4: Scan

Split the deduplicated company list into batches of BATCH_SIZE_SCAN (5).

Spawn **one `outreach-scanner` agent per batch**, all in parallel:

```
Scan the following companies for reviews and reputation data.

Companies:
<JSON array of this batch>

Write your results to: .mz/outreach/<run_name>/scan_batch_<N>.json
```

After ALL scanners complete:

1. Read all `scan_batch_*.json` files
1. Merge into a single array
1. Sort by `review_summary.avg_score` descending (companies with no data go to the end)
1. Write to `.mz/outreach/<run_name>/companies_scanned.json`
1. Write summary to `.mz/outreach/<run_name>/scan_summary.md`
1. Update state.json: `"phase": "scan_complete"`

______________________________________________________________________

## Phase 5: Enrich

Select the top `limit` companies from the sorted scanned list. Write this filtered list to `.mz/outreach/<run_name>/companies_to_enrich.json`.

Spawn a single `outreach-enrichment-orchestrator` agent to handle all enrichment:

```
Enrich the following companies with deep intelligence.

Companies file: .mz/outreach/<run_name>/companies_to_enrich.json
Strategy file: .mz/outreach/<run_name>/strategy.json
Output directory: .mz/outreach/<run_name>

For each company, dispatch 4 parallel agents:
- outreach-contact-finder (contacts, key people, LinkedIn)
- outreach-news-finder (press, funding, partnerships)
- outreach-growth-analyst (job postings, hiring, size, funding)
- outreach-tech-analyst (tech stack, engineering maturity)

Write per-company results to: .mz/outreach/<run_name>/enrich/<company_slug>/
Write the final merged result to: .mz/outreach/<run_name>/companies_enriched.json
```

After the orchestrator completes:

1. Verify `.mz/outreach/<run_name>/companies_enriched.json` exists and is non-empty
1. Update state.json: `"phase": "enrich_complete"`

______________________________________________________________________

## Phase 6: Report

Spawn a single `outreach-reporter` agent:

```
Generate the final outreach intelligence report.

Enriched company data: .mz/outreach/<run_name>/companies_enriched.json
Strategy: .mz/outreach/<run_name>/strategy.json
Original goal: <goal>

Scoring weights from strategy:
<scoring_weights from strategy.json>

Outreach angles from strategy:
<outreach_angles from strategy.json>

Write your report to:
- Markdown: .mz/outreach/<run_name>/report.md
- JSON: .mz/outreach/<run_name>/report.json
```

After the reporter completes:

1. Update state.json: `"phase": "complete", "completed_at": "<ISO timestamp>"`
1. Read the first 50 lines of `report.md` for the executive summary
1. Display to the user:
   - Path to the full report
   - Total companies analyzed
   - Number of sources consulted
   - Top 5 companies with their scores as a preview

______________________________________________________________________

## Resume Support

At the start of Phase 0, before creating anything, check if `.mz/outreach/<run_name>/state.json` already exists:

1. If it exists, read it and check the `phase` field
1. Resume from the next incomplete phase rather than restarting
1. Phases are idempotent — re-running a phase overwrites its output files

## Error Handling

- If any agent fails or returns empty results, log the error in state.json under `"errors": []` and continue with available data
- If ALL agents in a phase fail (zero results), stop the pipeline and report the failure with context
- Never fabricate data to fill gaps — incomplete results are better than false results
