# Phases 1-3: Strategy, Source Research, Scout + Dedup

## Phase 1: Strategy

Spawn `outreach-strategist`:

```
Analyze this outreach goal and define the search strategy:
Goal: "<goal>"
Sector hint: <sector or "not specified">
Write your strategy to: <RUN_DIR>/strategy.json
```

If a brief run was supplied (`BriefRun` is set in `state.md`), append its captured brief and local-climate dossier to the dispatch so the strategy is grounded in both:

```
Captured brief (from outreach-brief): <verbatim contents of <PROJECT_ROOT>/.mz/outreach/<brief_run>/brief.json>
Local business climate: <verbatim contents of <PROJECT_ROOT>/.mz/outreach/<brief_run>/climate.json — per industry × region economic, regulatory, deal, and pain-point signals, plus proposal hooks>
Fold the brief's offering, ICP, and geography into target_profile; fold the climate signals and proposal hooks into outreach_angles; and weight scoring toward the signals the climate surfaces.
```

Read `strategy.json`. Extract target profile, scoring weights, outreach angles, source hints.
Update `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` `Phase` field to `strategy_complete`.

Proceed to Phase 1.5 before launching Phase 2.

______________________________________________________________________

## Phase 1.5: User Approval of Strategy

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

### Why the gate matters

Phase 2 (source research) and Phase 3 (scout fan-out) dispatch parallel agents per source and per candidate company; each dispatch costs tokens and time. User approval at Phase 1.5 is the cost cap — the user confirms the strategy is right before the expensive fan-out runs. If feedback is provided, the strategy is revised before any discovery starts.

### Pre-read

Read `<PROJECT_ROOT>/.mz/outreach/<run_name>/strategy.json` with the Read tool. Capture the full file contents — target company profile, scoring weights, sources candidate list, signals to look for, and outreach angles — into context.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: strategy gate]`; `Status` stays `running`.

### Surface 1 — emit the plan message

Output the strategy verbatim as a normal markdown chat message. Emit the full verbatim contents of `<PROJECT_ROOT>/.mz/outreach/<run_name>/strategy.json` — do not substitute a path, summary, or placeholder. Structure:

````
## Strategy ready for review — outreach-research

```json
<verbatim contents of <PROJECT_ROOT>/.mz/outreach/<run_name>/strategy.json>
```

---
**Approve** → proceed to Phase 2 (source research)  ·  **Reject** → abort the task, no sources will be researched  ·  reply with feedback to revise
````

### Surface 2 — call AskUserQuestion

A short selector — do not re-embed the strategy in the question body, it lives in the plan message above:

- question: `The strategy above is ready for review.`
- header: `Strategy`
- options: **Approve** — proceed to Phase 2 (source research) · **Reject** — abort the task, no sources will be researched

### Response handling

- **Approve** → add `- strategy approved: .mz/outreach/<run_name>/strategy.json` under `## Decisions` in `state.md`, remove the `awaiting approval` entry from `what_remains`, set `Phase: strategy_approved`, and proceed to Phase 2.
- **Reject** → update `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` `Status` field to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → re-dispatch `outreach-strategist` with the user's feedback appended to the prompt, overwrite `strategy.json`, return to Surface 1, re-read `strategy.json`, and re-emit the entire plan message from scratch with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.
- **No answer** → set `Status: blocked`, keep `awaiting approval: strategy gate`, stop. A missing answer is never approval.

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

Validate >=1 source found. Update `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` `Phase` field to `sources_complete`.

______________________________________________________________________

## Phase 3: Scout + Dedup

### 3.1 Dispatch scouts

- **MAX_SCOUTS_PER_WAVE**: 6

Spawn one `outreach-scout` per source, in parallel **waves of ≤MAX_SCOUTS_PER_WAVE (6) concurrent agents per single assistant message**. If `sources.json` contains more than 6 sources, dispatch in sequential waves until every source has been scouted. Scouts are writer agents (they write `<RUN_DIR>/_scout/<source_slug>.json`). Wait for every agent in the wave to report, then check that each artifact exists on disk before using it.

Emit the pre-dispatch manifest right before each wave, and pass each role label as the agent's `description`. Skip both blocks for a wave of one agent:

```
Dispatching source scouting, wave <k> — <N> agents in parallel
Purpose: scout companies from each data source
- outreach-scout — <source name, ≤6 words>
- outreach-scout — <source name, ≤6 words>
```

```
Scout companies from this data source:
Source: <name>, URL: <url>, Type: <type>, Access notes: <notes>
Target profile: <target_profile>
Sector filter: <sectors>
Count limit: <ceil(limit / source_count), minimum 10>
Write results to: <RUN_DIR>/_scout/<source_slug>.json
```

Once every scout of a wave has reported, failed or been stopped, emit that wave's post-wave rollup before starting the next wave:

```
Wave complete (source scouting, wave <k>) — <returned>/<dispatched> agents returned
- outreach-scout: <STATUS> — <summary, ≤8 words>
```

An agent that returns no valid final `STATUS:` line is listed as `<agent>: NO RETURN BLOCK` and counted as not returned.

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
1. Update `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` — set `Phase` to `scout_complete` and add a `CompaniesFound` field with the count

Proceed to Phase 4. Read `phases/enrichment_and_report.md`.
