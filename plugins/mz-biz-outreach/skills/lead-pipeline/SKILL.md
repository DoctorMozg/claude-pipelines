---
name: lead-pipeline
description: Full autonomous outreach pipeline — analyzes goal, discovers sources, scouts companies, scans reputations, enriches with contacts/news/growth/tech data, scores leads, writes per-company dossier cards, and produces an executive summary report. Provide a target description as the argument.
argument-hint: <target description> [sector:filter] [limit:N]
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, WebFetch, WebSearch
---

# Lead Generation Pipeline

You are an orchestrator that drives a full business outreach intelligence pipeline. You receive an outreach goal and autonomously define strategy, research sources, discover companies, scan reputations, enrich with deep intelligence, score leads, write per-company dossier cards, and produce an executive summary report.

Every company gets exactly two permanent files: a `.json` (machine-readable, progressively enriched) and a `.md` (human-readable dossier card). No bulk JSON arrays.

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
└── report.md                      # executive summary + scored ranking + card references
```

## Phase Overview

| #   | Phase           | Agent(s)                                     | Output                         |
| --- | --------------- | -------------------------------------------- | ------------------------------ |
| 0   | Setup           | —                                            | state.json, directories        |
| 1   | Strategy        | `outreach-strategist`                        | strategy.json                  |
| 2   | Source Research | `outreach-source-researcher`                 | sources.json                   |
| 3   | Scout + Dedup   | N × `outreach-scout` (parallel)              | companies/\<slug>.json each    |
| 4   | Scan            | N × `outreach-scanner` (parallel, 1/company) | updates companies/\<slug>.json |
| 5   | Enrich          | `outreach-enrichment-orchestrator`           | updates companies/\<slug>.json |
| 6   | Score           | inline (orchestrator)                        | updates companies/\<slug>.json |
| 7   | Write Cards     | N × `outreach-card-writer` (all parallel)    | companies/\<slug>.md each      |
| 8   | Report          | `outreach-reporter`                          | report.md                      |

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

______________________________________________________________________

## Phase 1: Strategy

Spawn `outreach-strategist`:

```
Analyze this outreach goal and define the search strategy:
Goal: "<goal>"
Sector hint: <sector or "not specified">
Write your strategy to: <RUN_DIR>/strategy.json
```

Read `strategy.json`. Extract target profile, scoring weights, outreach angles, source hints.
Update state: `"phase": "strategy_complete"`.

______________________________________________________________________

## Phase 2: Source Research

Spawn `outreach-source-researcher`:

```
Research the best business directories for finding companies matching this target profile:
Target: <target_profile>
Sectors: <sectors>
Geography: <geography>
Source hints: <source_hints>
Write results to: <RUN_DIR>/sources.json
```

Validate ≥1 source found. Update state: `"phase": "sources_complete"`.

______________________________________________________________________

## Phase 3: Scout + Dedup

### 3.1 Dispatch scouts

Spawn one `outreach-scout` per source, all parallel:

```
Scout companies from this data source:
Source: <name>, URL: <url>, Type: <type>, Access notes: <notes>
Target profile: <target_profile>
Sector filter: <sectors>
Count limit: <ceil(limit / source_count), minimum 10>
Write results to: <RUN_DIR>/_scout/<source_slug>.json
```

### 3.2 Deduplicate and fan out

After all scouts complete:

1. Read all `_scout/*.json` files, merge into a single array
1. Deduplicate by domain: keep the entry with the most non-null fields, merge `source` names
1. For each unique company, derive a slug:
   - If domain exists: strip TLD and protocol, replace dots/special chars with hyphens (e.g., `acme-corp.com` → `acme-corp`)
   - If no domain: slugify the company name (lowercase, replace spaces/special with hyphens, max 30 chars)
   - On collision: append `-2`, `-3`, etc.
1. Write each company as `companies/<slug>.json`:

```json
{
  "slug": "<slug>",
  "name": "...", "domain": "...", "sector": "...",
  "location": "...", "founded": "...", "description": "...",
  "sources": ["Source A", "Source B"],
  "source_urls": ["..."],
  "reviews": null, "review_summary": null,
  "contacts": null, "news": null,
  "growth": null, "tech_profile": null,
  "intelligence_score": null, "score_breakdown": null
}
```

5. Write `scout_summary.md` (total found, per-source breakdown, dedup count)
1. Delete `_scout/` temp directory
1. Update state: `"phase": "scout_complete", "companies_found": N`

______________________________________________________________________

## Phase 4: Scan

Dispatch one `outreach-scanner` per company, **all in parallel**:

```
Scan this company for reviews and reputation data.
Company file: <RUN_DIR>/companies/<slug>.json
Read the company JSON, scan review platforms, then write the updated JSON
back to the same path with reviews and review_summary fields populated.
```

After all scanners complete:

1. Read each company JSON and verify `review_summary` is populated
1. If `limit` is set and companies exceed it: sort by `review_summary.avg_score` descending, select top `limit`. Mark remaining as `"enrichment_skipped": true` in their JSONs (not deleted — kept for reference).
1. Write `scan_summary.md` (review distribution, sentiment breakdown, companies selected for enrichment)
1. Update state: `"phase": "scan_complete"`

______________________________________________________________________

## Phase 5: Enrich

Spawn `outreach-enrichment-orchestrator`:

```
Enrich companies with deep intelligence.

Companies directory: <RUN_DIR>/companies/
Temp output directory: <RUN_DIR>/_enrichment/
Strategy file: <RUN_DIR>/strategy.json

For each company JSON in companies/ (skip any with enrichment_skipped: true):
1. Read the company JSON
2. Create _enrichment/<slug>/
3. Dispatch 4 parallel agents:
   - outreach-contact-finder → _enrichment/<slug>/contacts.json
   - outreach-news-finder → _enrichment/<slug>/news.json
   - outreach-growth-analyst → _enrichment/<slug>/growth.json
   - outreach-tech-analyst → _enrichment/<slug>/tech.json
4. Read temps, merge into the company JSON (contacts, news, growth, tech_profile fields)
5. Write updated JSON back to companies/<slug>.json
6. Delete _enrichment/<slug>/

After all companies: delete _enrichment/ directory.
```

Verify enrichment by spot-checking a few company JSONs. Update state: `"phase": "enrich_complete"`.

______________________________________________________________________

## Phase 6: Score (Inline)

The orchestrator computes intelligence scores — no subagent needed.

1. Read `strategy.json` → `scoring_weights` (percentage-based, sum to 100)
1. For each company JSON in `companies/` (skip enrichment-skipped):
   a. Read the JSON
   b. Compute per-factor scores (0-100 scale):

| Factor               | Computation                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| data_completeness    | % of enrichment fields (reviews, contacts, news, growth, tech_profile) that are non-null        |
| review_reputation    | avg_score mapping: 5.0→100, 4.0→80, 3.0→60, \<3.0→40, no_data→20                                |
| contact_availability | Key people with LinkedIn: +30 each (cap 2). Email: +20. Phone: +10. Social: +10. Min 0, max 100 |
| growth_signals       | Trajectory: rapid→80, steady→50, stable→30, declining→10. Job postings>10: +10. Funding: +10    |
| sector_relevance     | Exact sector match→100, adjacent→60, unrelated→20                                               |
| outreach_feasibility | Decision-maker with LinkedIn→50, has email→30, has phone→10, nothing→10                         |

c. Weighted score: `Σ(factor_score × weight / 100)`, round to integer (0-100)
d. Write `intelligence_score` and `score_breakdown` (per-factor scores + weights) into the JSON

3. Update state: `"phase": "scored"`

______________________________________________________________________

## Phase 7: Write Cards

Dispatch ALL `outreach-card-writer` agents at once — one per non-skipped company, no parallelism cap. Card writers only read JSONs and write separate `.md` files, so there is zero conflict risk.

```
Write a complete company dossier card.
Company JSON: <RUN_DIR>/companies/<slug>.json
Strategy file: <RUN_DIR>/strategy.json
Output: <RUN_DIR>/companies/<slug>.md
```

After all card writers complete, verify each non-skipped company has a `.md` card.
Update state: `"phase": "cards_written"`.

______________________________________________________________________

## Phase 8: Report

Spawn `outreach-reporter`:

```
Generate the executive summary report.
Companies directory: <RUN_DIR>/companies/
Strategy: <RUN_DIR>/strategy.json
Original goal: <goal>
Output: <RUN_DIR>/report.md
```

After the reporter completes:

1. Update state: `"phase": "complete", "completed_at": "<ISO>"`
1. Display to the user:
   - Path to `report.md`
   - Path to `companies/` directory (for browsing individual cards)
   - Total companies analyzed and scored
   - Top 5 by score as a quick preview

______________________________________________________________________

## Resume Support

Before creating anything in Phase 0, check if `state.json` exists. If it does, read `phase` and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent fails or returns empty: log in `state.json` under `"errors": []`, continue with available data
- ALL agents in a phase fail (zero results): stop the pipeline and report the failure
- Never fabricate data — incomplete results are better than false results
- Corrupted company JSON during any phase: log the error, skip that company, continue
