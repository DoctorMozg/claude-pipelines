# Phases 1-3: Strategy, Source Research, Scout + Dedup

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

Validate >=1 source found. Update state: `"phase": "sources_complete"`.

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

Proceed to Phase 4. Read `phases/enrichment_and_report.md`.
