# Phases 4-8: Scan, Enrich, Score, Cards, Report

## Phase 4: Scan

Dispatch one `outreach-scanner` per company in parallel **waves of ≤6 concurrent agents per single assistant message**. Scanners are writer agents (they rewrite the company JSON), so the 6-agent wave cap applies. Run sequential waves until every company has been scanned. Never dispatch with `run_in_background: true` — backgrounded writer agents have their writes silently dropped.

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
1. Update `.mz/task/<task_name>/state.md` `Phase` field to `scan_complete`

______________________________________________________________________

## Phase 5: Enrich

Spawn `outreach-enrichment-orchestrator`:

```
Enrich companies with deep intelligence.

Companies directory: <RUN_DIR>/companies/
Temp output directory: <RUN_DIR>/_enrichment/
Strategy file: <RUN_DIR>/strategy.json

For each company JSON in companies/ (skip any with enrichment_skipped: true), process **one company at a time** — do not parallelize across companies:
1. Read the company JSON
1. Create _enrichment/<slug>/
1. Dispatch 4 parallel agents in a single assistant message (one wave of exactly 4 concurrent agents — well under the 6-agent cap):
   - outreach-contact-finder → _enrichment/<slug>/contacts.json
   - outreach-news-finder → _enrichment/<slug>/news.json
   - outreach-growth-analyst → _enrichment/<slug>/growth.json
   - outreach-tech-analyst → _enrichment/<slug>/tech.json
1. Wait for all 4 agents to return (artifact files present on disk). Never dispatch with `run_in_background: true` — the 4 agents are writer agents.
1. Read temps, merge into the company JSON (contacts, news, growth, tech_profile fields)
1. Write updated JSON back to companies/<slug>.json
1. Delete _enrichment/<slug>/

The 4-agent enrichment wave stays ≤6 per the global wave cap; serializing across companies keeps the cap respected while the 4 per-company agents remain in a single wave.

After all companies: delete _enrichment/ directory.
```

Verify enrichment by spot-checking a few company JSONs. Update `.mz/task/<task_name>/state.md` `Phase` field to `enrich_complete`.

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

c. Weighted score: `sum(factor_score * weight / 100)`, round to integer (0-100)
d. Write `intelligence_score` and `score_breakdown` (per-factor scores + weights) into the JSON

3. Update `.mz/task/<task_name>/state.md` `Phase` field to `scored`

______________________________________________________________________

## Phase 7: Write Cards

Dispatch `outreach-card-writer` agents one per non-skipped company, in parallel **waves of ≤6 concurrent agents per single assistant message**. Card writers only read JSONs and write separate `.md` files, so there is zero conflict risk, but the 6-agent wave cap from `CLAUDE.md` Plugin Authoring Conventions still applies to every parallel dispatch. Run sequential waves until every non-skipped company has a card. Never dispatch with `run_in_background: true` — card writers are writer agents, and backgrounded writes are silently dropped.

```
Write a complete company dossier card.
Company JSON: <RUN_DIR>/companies/<slug>.json
Strategy file: <RUN_DIR>/strategy.json
Output: <RUN_DIR>/companies/<slug>.md
```

After all card writers complete, verify each non-skipped company has a `.md` card.
Update `.mz/task/<task_name>/state.md` `Phase` field to `cards_written`.

______________________________________________________________________

## Phase 8: Report

Spawn `outreach-reporter`:

```
Generate the executive summary report.
Companies directory: <RUN_DIR>/companies/
Strategy: <RUN_DIR>/strategy.json
Original goal: <goal>
Output: <RUN_DIR>/<YYYY_MM_DD>_outreach_<goal_slug>.md
Report naming convention: <YYYY_MM_DD>_outreach_<goal_slug><_vN>.md (append _v2, _v3 if same base name exists)
```

After the reporter completes:

1. Update `.mz/task/<task_name>/state.md` — set `Phase` to `complete` and add a `CompletedAt` field with the ISO timestamp
1. Display to the user:
   - Path to the report
   - Path to `companies/` directory (for browsing individual cards)
   - Total companies analyzed and scored
   - Top 5 by score as a quick preview
