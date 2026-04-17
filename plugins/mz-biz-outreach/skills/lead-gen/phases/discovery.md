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
Update `.mz/task/<task_name>/state.md` `Phase` field to `strategy_complete`.

Proceed to Phase 1.5 before launching Phase 2.

______________________________________________________________________

## Phase 1.5: User Approval of Strategy

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

### What to present

The user must see, verbatim or summarized from `strategy.json`:

1. **Target company profile** — industry, size, geography, stage.
1. **Scoring weights** — how candidates will be ranked.
1. **Sources candidate list** — which directories/platforms will be queried.
1. **Signals to look for** — growth signals, hiring patterns, news triggers.
1. **Outreach angles** — what the eventual message will focus on.

### Why the gate matters

Phase 2 (source research) and Phase 3 (scout fan-out) dispatch parallel agents per source and per candidate company; each dispatch costs tokens and time. User approval at Phase 1.5 is the cost cap — the user confirms the strategy is right before the expensive fan-out runs. If feedback is provided, the strategy is revised before any discovery starts.

### Presentation block

Before invoking AskUserQuestion, emit a text block to the user:

```
**Strategy ready for review**
The lead-generation strategy has been defined. Below are the target profile, search criteria, scoring weights, sources list, and signals that will drive discovery and outreach.

- **Approve** → proceed to Phase 2 (source research)
- **Reject** → abort the task, no sources will be researched
- **Feedback** → provide changes, strategy will be revised and re-presented
```

### AskUserQuestion prompt

Use AskUserQuestion with the following message:

```
The target profile, search criteria, scoring weights, sources list, and signals for this lead-generation task:

<contents of strategy.json, formatted as the five points above>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

### Response handling

- **"approve"** → update `.mz/task/<task_name>/state.md` `Phase` field to `strategy_approved` and proceed to Phase 2.
- **"reject"** → update `.mz/task/<task_name>/state.md` `Status` field to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-dispatch `outreach-strategist` with the user's feedback appended to the prompt, overwrite `strategy.json`, return to this gate and re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

All five elements above (delegation guard, presentation, AskUserQuestion prompt ending with the canonical reply line, three-bullet response handling, explicit loop language) are required per `SKILL_GUIDELINES.md`.

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

Validate >=1 source found. Update `.mz/task/<task_name>/state.md` `Phase` field to `sources_complete`.

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
1. Update `.mz/task/<task_name>/state.md` — set `Phase` to `scout_complete` and add a `CompaniesFound` field with the count

Proceed to Phase 4. Read `phases/enrichment_and_report.md`.
