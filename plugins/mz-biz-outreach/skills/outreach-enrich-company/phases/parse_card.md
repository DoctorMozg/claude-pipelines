# Phase 0: Setup — Phase 1: Parse Card

Read `SKILL.md` first. Argument parsing and Source resolution are in `<SKILL_DIR>/references/argument-parsing.md`; the directory layout and the `task_name` and `<run_dir>` rules are in `<SKILL_DIR>/references/directory-structure.md`. Read both before Phase 0.

## Resume Support

Before creating anything in Phase 0, run Source Resolution to derive `company_slug` and `source_path`, then check if `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` and `SourcePath` fields and resume from the next incomplete phase:

- `Phase: 0` → restart from Phase 0 with freshly resolved `source_path` (do not trust the stored `SourcePath` since the prior run did not complete validation).
- `Phase: card_parsed` → resume from Phase 2 (or Phase 3 if `enrich_mode == "skip"`). Use the stored `SourcePath`.
- `Phase: enrichment_complete` → resume from Phase 3 (or jump to Phase 5 if `enrich_mode == "only"`). Use the stored `SourcePath`.
- `Phase: briefs_complete` → resume from Phase 3 drafting. Use the stored `SourcePath`.
- `Phase: drafts_complete` → resume from Phase 4. Use the stored `SourcePath`.
- `Phase: naturalize_complete` → resume from Phase 5. Use the stored `SourcePath` for the read; compute `target_path` fresh from today's date.
- `Phase: complete` → no work to do; emit verification block from state. If the freshly resolved `source_path` differs from state's `TargetPath` (e.g., user re-invoked on a stale path or a new day passed), treat it as a new run and restart from Phase 0 with a new `task_name` (`_v2`, `_v3`).

All phases are idempotent — re-running overwrites output files. Phase 5 writes to `target_path` (today's active path), replacing any prior file at that exact location; the post-write cleanup step removes the source if it differs.

## Phase 0: Setup + card validation

Resolve `PROJECT_ROOT` with the command in Constants, before any `cd` or worktree switch, and use it for every `.mz/` path below.

Parse arguments. Resolve `user_path`, `channels_override`, `sender_override`, `enrich_mode`. Run Source Resolution (see Argument Parsing) to derive `company_slug` and `source_path`. Verify `source_path` exists and parses as a canonical company card.

Derive:

- `company_slug` — already set by Source Resolution (stripped of any date prefix and `.md`).
- `task_name` = `<YYYY_MM_DD>_outreach_enrich_<company_slug>` (truncate `<company_slug>` to 30 chars if needed). Collision: `_v2`, `_v3`.
- `task_dir` = `<PROJECT_ROOT>/.mz/task/<task_name>/`.
- `run_dir` = if `source_path` is under `.mz/outreach/<run>/companies/`, then `dirname(dirname(source_path))`; otherwise (active path) the most-recently-modified `<PROJECT_ROOT>/.mz/outreach/<run>/` directory that contains a `strategy.json`, falling back to `default` voice if none found.

```bash
mkdir -p "<PROJECT_ROOT>/.mz/task/<task_name>/enrichment"
mkdir -p "<PROJECT_ROOT>/.mz/task/<task_name>/briefs"
mkdir -p "<PROJECT_ROOT>/.mz/task/<task_name>/profiles"
mkdir -p "<PROJECT_ROOT>/.mz/task/<task_name>/drafts"
mkdir -p "<PROJECT_ROOT>/.mz/outreach/active"
```

Write `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`:

```yaml
schema_version: 2
Status: running
Phase: 0
Started: <ISO timestamp>
phase_complete: false
what_remains: []
UserPath: <user-supplied path verbatim>
SourcePath: <resolved path actually being read>
CompanySlug: <slug>
RunDir: <run_dir or "default">
ChannelsOverride: <value or "auto">
SenderOverride: <value or "strategy.json|default">
EnrichMode: <both | only | skip>
BriefRun: <brief_run or null>
PersonalityMode: <on | off>
```

## Phase 1: Parse card + light web enrichment

Read the card. Extract structured data — do this with normal markdown reading, not a regex parser. Capture:

- **Company**: name (from H1), domain, sector, location, founded, size, score (from the metadata header lines).
- **Overview**: the `## Overview` paragraph.
- **Key Contacts**: every numbered entry under `## Key Contacts`. Each entry is `**<Name>** — <Title> — [LinkedIn](<url>) — <relevance>`. Extract name, title, LinkedIn URL, relevance line. Also capture the trailing `**Emails**:`, `**Phone**:`, `**Company LinkedIn**:` lines. Cap at 5 contacts.
- **Recent News**: numbered entries under `## Recent News & Timing Signals`. Each: `**<Title>** (<date>, <category>, <timing_relevance> timing) — <outreach_implication>`. Keep top 3 by `timing_relevance` (high first).
- **Outreach Recommendation**: the synthesizing paragraph plus the three labeled lines `**Best contact**:`, `**Best angle**:`, `**Timing**:`.
- **Technology Profile**: stack list, maturity, GitHub URL, tech blog URL.
- **Growth Signals**: trajectory, open roles, funding (if present).
- **Red Flags**: any bulleted items (or "None identified").

Persist the parsed structure to `<PROJECT_ROOT>/.mz/task/<task_name>/card_parsed.json` so Phase 2 subagents can read it without re-parsing the markdown:

```json
{
  "company": { "name": "...", "slug": "...", "domain": "...", "sector": "...", "location": "...", "founded": "...", "size": "..." },
  "overview": "<paragraph text>",
  "key_contacts": [ { "name": "...", "title": "...", "linkedin_url": "...", "email": "...", "relevance": "..." } ],
  "recent_news": [ { "title": "...", "date": "...", "category": "...", "timing_relevance": "...", "outreach_implication": "..." } ],
  "outreach_recommendation": { "summary": "...", "best_contact": "...", "best_angle": "...", "timing": "..." },
  "tech_profile": { "stack": ["..."], "maturity": "...", "github_url": "...", "tech_blog_url": "..." },
  "growth_signals": { "trajectory": "...", "open_roles": ["..."], "funding": "..." },
  "red_flags": ["..."]
}
```

Read `<run_dir>/strategy.json` if it exists. Capture the `sender_voice` (or `outreach_strategy.sender_voice`) and `outreach_angles` fields. If the file is missing OR the field is empty, use these defaults:

- `sender_voice` = `"Professional, concise, plain-spoken. No marketing register, no hype. First-person singular. Direct request, one CTA per letter."`
- `outreach_angles` = `["Value-first introduction citing one verified personalization signal from the card or fresh research."]`

If `sender_override` was supplied as an argument, it overrides the strategy.json value (inline text → used directly; path → read the file).

Record `strategy_source` per brief: `strategy.json` if loaded from disk, `default` if fallback applied, `sender_override` if argument was used. If `default`, the final STATUS will be `DONE_WITH_CONCERNS`.

### Local-climate context

If `brief_run` was supplied, read `<PROJECT_ROOT>/.mz/outreach/<brief_run>/climate.json` and select the combo whose `industry` and `region` best match the card's sector and location (prefer an exact region match, then industry; if none match, skip climate context and letters fall back to company data). Capture the matched combo's `signals` and `top_outreach_angles` as `climate_context`, carried into Phase 3 brief-building. If the file is missing, warn and continue without it.

### Light web enrichment

This is a small fast pre-pass for the orchestrator to grab per-contact signals the Phase 2 subagents won't touch. The deep, multi-source enrichment happens in Phase 2 via subagents. Hard cap here: 6 calls.

Run a single parallel wave of WebSearch calls:

1. 1 × WebSearch per Key Contact (up to 5) — public activity. Query: `"<contact full name>" "<company name>" linkedin OR podcast OR interview OR keynote`.
1. 1 × WebSearch — anchor query for cross-referencing in Phase 2. Query: `"<company name>" news <current year>`.

Capture per-contact signal strings (1–2 lines each, verbatim from the search snippet). Discard anything that cannot be cited. These signals seed Phase 3 brief-building; they are not written into the card.

Record the total number of light-pass web calls — surface in the final verification block.

Update `state.md` Phase field to `card_parsed`. If `enrich_mode == "skip"`, advance directly to Phase 3 (handoff to `<SKILL_DIR>/phases/draft_letters.md`). Otherwise advance to Phase 2 (handoff to `<SKILL_DIR>/phases/deep_enrichment.md`).
