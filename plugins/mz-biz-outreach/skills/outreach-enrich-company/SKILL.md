---
name: outreach-enrich-company
description: ALWAYS invoke when the user wants to deepen the dossier on a company card AND/OR generate LinkedIn/email outreach letters from it. Fans out 5 enrichment subagents (news, tech, growth, reputation, contacts) to fill gaps left by the base research, then drafts and naturalizes one letter per Key Contact. Triggers - "enrich <card>", "go deeper on <card>", "deepen research on <company>", "write outreach letters for <card>", "draft messages from <card>", "generate letters for this card".
argument-hint: "<path/to/company_card.md>" [channels:email|linkedin|both] [sender:<voice text or path>] [enrich:only|skip]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Outreach Enrich Company

## Overview

You are an orchestrator that takes a company card produced by `/outreach-research` and does two things, in this order:

1. **Deepen the dossier**. Fan out five specialist enrichment subagents in parallel — `outreach-news-finder`, `outreach-tech-analyst`, `outreach-growth-analyst`, `outreach-scanner`, `outreach-contact-finder` — each instructed to find data **not already in the card** (gap-filling, not duplicating). Their findings are merged into a new `## Deeper Intelligence` section appended to the card.
1. **Draft outreach letters**. Using the original card data plus the deeper intelligence as personalization fuel, draft one letter per named Key Contact via `expert-copywriter`, then mandatorily naturalize each via `expert-naturalizer`. The letters are appended as a `## Outreach Letters` section inside the card.

The whole pipeline is fully automatic — no approval gates, no mid-run prompts. The user invokes the skill, the skill enriches and writes letters, the card now holds them both.

## When to Use

Invoke when the user has a company card (produced by `/outreach-research`, lives at `.mz/outreach/<run>/companies/<slug>.md`) and wants either richer company intelligence, outreach letters, or both. Trigger phrases:

- "enrich `.mz/outreach/.../companies/<slug>.md` and write letters"
- "deepen the research on this card"
- "go deeper on `<company>` and draft outreach"
- "write outreach letters for `<card>`"
- "generate letters from this card"

### When NOT to use

- The user has only a company name or domain and no card — run `/outreach-research` first (single-company mode if they want only one).
- The user wants to discover companies first — use `/outreach-research`.
- The user wants recruiter contacts for a job application — use `/job-recruiter-info` in mz-job-outreach.
- The user wants general marketing copy (landing pages, announcements, social) — use `/copywrite` from mz-creative.
- The user wants letters written to a separate location than the card — this skill only writes back into the card.

## Input

- `$ARGUMENTS` — Required: an absolute or repo-relative path to a company card `.md` file. Two accepted shapes:
  - **Research baseline**: `.mz/outreach/<run>/companies/<slug>.md` — direct output of `/outreach-research`. First activation moves it to `active/`.
  - **Active**: `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` — a card already activated by this skill or `/outreach-update-card`. The date prefix is the last interaction date; this run updates it to today.
- Optional modifiers (case-insensitive, order-independent):
  - `channels:email|linkedin|both` — overrides per-contact channel auto-detection. Default: best channel per contact (email if known, else LinkedIn DM, else skip).
  - `sender:<inline text or path>` — overrides the sender voice. Inline text becomes the voice description; a path is read as a sender bio markdown file. Default: read `<run>/strategy.json` `sender_voice` field if present.
  - `enrich:only` — run the deep-enrichment phase and skip letter drafting (card gets `## Deeper Intelligence` but no `## Outreach Letters`).
  - `enrich:skip` — skip the deep-enrichment phase and draft letters directly from the existing card content only.
  - Default (neither flag): both phases run.

If `$ARGUMENTS` is empty or no source can be resolved (see Source Resolution below), emit `STATUS: BLOCKED` with a clear message and stop.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **user_path** — the path token (everything not matching a parameter pattern). Must end in `.md`.
- **channels_override** — from `channels:<value>` (default: unset → per-contact auto-detect).
- **sender_override** — from `sender:<value>` (default: unset → use strategy.json or fallback voice).
- **enrich_mode** — from `enrich:<value>`: `only`, `skip`, or unset (default unset = both phases run).

### Source resolution

Extract the company slug from `user_path`'s basename:

- If the basename matches `<YYYY-MM-DD>_<slug>.md` (active path), `company_slug` = the part after the date prefix.
- Otherwise (`<slug>.md`), `company_slug` = the basename minus `.md`.

Then resolve `source_path` (the file actually read and updated by this run):

```bash
mkdir -p .mz/outreach/active
find .mz/outreach/active -maxdepth 1 -type f \
  -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<company_slug>.md' 2>/dev/null | head -1
```

- **If found** → `source_path` = the active path returned. The user-supplied path is ignored in favor of the active version (which holds the canonical accumulated history). The user may have passed a now-deleted research-baseline path; the active version is authoritative.
- **If not found** → `source_path` = `user_path`. The card has not been activated yet; this run will activate it.

Validate the card at `source_path` before any other work:

1. The file exists (Read succeeds).
1. The first non-empty line starts with `# ` (H1 = company name).
1. The body contains H2 headers matching the canonical card shape — at minimum `## Overview`, `## Key Contacts`, `## Outreach Recommendation` must all be present. If any are missing, emit `STATUS: BLOCKED` with the list of missing headers.

## Directory Structure

- **State** — `.mz/task/<task_name>/state.md`. Source of truth across phases.
- **Card snapshot** — `.mz/task/<task_name>/card_parsed.json`. Structured extract of the source card, consumed by the deep-enrichment subagents in Phase 2 so they know what is ALREADY documented.
- **Enrichment artifacts** — `.mz/task/<task_name>/enrichment/<agent_slug>.json`. One JSON per Phase 2 subagent (`news.json`, `tech.json`, `growth.json`, `reputation.json`, `contacts.json`).
- **Briefs** — `.mz/task/<task_name>/briefs/<contact_slug>.json`. One brief per contact selected for drafting.
- **Drafts** — `.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md`. One draft file per (contact, channel) pair. Each draft carries YAML frontmatter (`subject`, `channel`, `recipient`) followed by the body.
- **Card lifecycle** — the card ends this run at `target_path = .mz/outreach/active/<today>_<company_slug>.md`. If `source_path != target_path`, the source file is deleted in the final card-rewrite phase (move semantics). Research-baseline cards at `.mz/outreach/<run>/companies/<slug>.md` and stale-dated active cards (`active/<other-date>_<slug>.md`) are removed by this run.

`task_name` follows `<YYYY_MM_DD>_outreach_enrich_<company_slug>` where `<company_slug>` is derived in Source Resolution (slug without date prefix or `.md`). Same-day collisions append `_v2`, `_v3`.

`<run_dir>` = the directory containing `source_path` when the card is still at its research-baseline location (typically `.mz/outreach/<run>/companies/`). The sibling `strategy.json` lives at `<run_dir>/../strategy.json` — read it from there for sender voice and outreach angles. When `source_path` is already an active path, `<run_dir>` falls back to the most-recently-modified `.mz/outreach/<run>/` directory containing a `strategy.json` (or `default` voice if none can be located).

## Core Process

### Phase Overview

| #   | Phase                             | Agent(s)                                                                                                                  | Details                        |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| 0   | Setup + card validation           | — (orchestrator)                                                                                                          | Inline below                   |
| 1   | Parse card + light web enrichment | — (orchestrator + WebSearch)                                                                                              | Inline below                   |
| 2   | Deep enrichment via subagents     | `outreach-news-finder`, `outreach-tech-analyst`, `outreach-growth-analyst`, `outreach-scanner`, `outreach-contact-finder` | `phases/deep_enrichment.md`    |
| 3   | Draft letters                     | `expert-copywriter`                                                                                                       | `phases/draft_and_finalize.md` |
| 4   | Naturalize letters                | `expert-naturalizer`                                                                                                      | `phases/draft_and_finalize.md` |
| 5   | Rewrite card (deeper + letters)   | — (orchestrator, Read + Write)                                                                                            | `phases/draft_and_finalize.md` |
| 6   | Verification summary              | — (orchestrator)                                                                                                          | Inline below                   |

Read `phases/deep_enrichment.md` when you reach Phase 2 and `phases/draft_and_finalize.md` when you reach Phase 3. If `enrich_mode == "only"`, Phases 3 and 4 are skipped; Phase 5 still runs to append the `## Deeper Intelligence` section. If `enrich_mode == "skip"`, Phase 2 is skipped; Phase 5 only appends the `## Outreach Letters` section.

### Phase 0: Setup + card validation

Parse arguments. Resolve `user_path`, `channels_override`, `sender_override`, `enrich_mode`. Run Source Resolution (see Argument Parsing) to derive `company_slug` and `source_path`. Verify `source_path` exists and parses as a canonical company card.

Derive:

- `company_slug` — already set by Source Resolution (stripped of any date prefix and `.md`).
- `task_name` = `<YYYY_MM_DD>_outreach_enrich_<company_slug>` (truncate `<company_slug>` to 30 chars if needed). Collision: `_v2`, `_v3`.
- `task_dir` = `.mz/task/<task_name>/`.
- `run_dir` = if `source_path` is under `.mz/outreach/<run>/companies/`, then `dirname(dirname(source_path))`; otherwise (active path) the most-recently-modified `.mz/outreach/<run>/` directory that contains a `strategy.json`, falling back to `default` voice if none found.

```bash
mkdir -p .mz/task/<task_name>/enrichment
mkdir -p .mz/task/<task_name>/briefs
mkdir -p .mz/task/<task_name>/drafts
mkdir -p .mz/outreach/active
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Outreach Enrich Company State
- **Status**: running
- **Phase**: 0
- **Started**: <ISO timestamp>
- **UserPath**: <user-supplied path verbatim>
- **SourcePath**: <resolved path actually being read>
- **CompanySlug**: <slug>
- **RunDir**: <run_dir or "default">
- **ChannelsOverride**: <value or "auto">
- **SenderOverride**: <value or "strategy.json|default">
- **EnrichMode**: <both | only | skip>
```

### Phase 1: Parse card + light web enrichment

Read the card. Extract structured data — do this with normal markdown reading, not a regex parser. Capture:

- **Company**: name (from H1), domain, sector, location, founded, size, score (from the metadata header lines).
- **Overview**: the `## Overview` paragraph.
- **Key Contacts**: every numbered entry under `## Key Contacts`. Each entry is `**<Name>** — <Title> — [LinkedIn](<url>) — <relevance>`. Extract name, title, LinkedIn URL, relevance line. Also capture the trailing `**Emails**:`, `**Phone**:`, `**Company LinkedIn**:` lines. Cap at 5 contacts.
- **Recent News**: numbered entries under `## Recent News & Timing Signals`. Each: `**<Title>** (<date>, <category>, <timing_relevance> timing) — <outreach_implication>`. Keep top 3 by `timing_relevance` (high first).
- **Outreach Recommendation**: the synthesizing paragraph plus the three labeled lines `**Best contact**:`, `**Best angle**:`, `**Timing**:`.
- **Technology Profile**: stack list, maturity, GitHub URL, tech blog URL.
- **Growth Signals**: trajectory, open roles, funding (if present).
- **Red Flags**: any bulleted items (or "None identified").

Persist the parsed structure to `.mz/task/<task_name>/card_parsed.json` so Phase 2 subagents can read it without re-parsing the markdown:

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

#### Light web enrichment

This is a small fast pre-pass for the orchestrator to grab per-contact signals the Phase 2 subagents won't touch. The deep, multi-source enrichment happens in Phase 2 via subagents. Hard cap here: 6 calls.

Run a single parallel wave of WebSearch calls:

1. 1 × WebSearch per Key Contact (up to 5) — public activity. Query: `"<contact full name>" "<company name>" linkedin OR podcast OR interview OR keynote`.
1. 1 × WebSearch — anchor query for cross-referencing in Phase 2. Query: `"<company name>" news <current year>`.

Capture per-contact signal strings (1–2 lines each, verbatim from the search snippet). Discard anything that cannot be cited. These signals seed Phase 3 brief-building; they are not written into the card.

Record the total number of light-pass web calls — surface in the final verification block.

Update `state.md` Phase field to `card_parsed`. If `enrich_mode == "skip"`, advance directly to Phase 3 (handoff to `phases/draft_and_finalize.md`). Otherwise advance to Phase 2 (handoff to `phases/deep_enrichment.md`).

### Phase 6: Verification summary

After Phase 5 completes, emit a visible block:

```
Outreach enrich-company done.
Source (read from):     <source_path>
Card (final):           <target_path = .mz/outreach/active/<today>_<slug>.md>
Relocated:              <yes | no>     # yes if source_path != target_path
Task dir:               .mz/task/<task_name>/
Enrichment mode:        <both | only | skip>
Subagents dispatched:   <N>    (capped at 5)
Subagents failed:       <M>
Deeper-intel fields:    <list of populated subsections (e.g. news, tech, growth, reputation, contacts)>
Contacts drafted:       <N>   (channels: <breakdown>)   # 0 if enrich_mode == only
Contacts skipped:       <M>   (no contact route)
Light web calls:        <K>   (cap 6)
Naturalize reverted:    <R>   (drafts where naturalize was rolled back)
Strategy source:        <strategy.json | default | sender_override>
STATUS: <DONE | DONE_WITH_CONCERNS>
```

`STATUS: DONE_WITH_CONCERNS` whenever any of: `strategy_source == default`, any contact was skipped, any draft was naturalize-reverted, any copywriter dispatch failed, any web call returned an error, any enrichment subagent returned `NEEDS_CONTEXT`/`BLOCKED`, the light-pass cap was hit and contacts had to drop, the relocation failed to delete the source file.

## Techniques

Techniques: delegated to `phases/deep_enrichment.md` (Phase 2) and `phases/draft_and_finalize.md` (Phases 3–5).

## Common Rationalizations

N/A — orchestration skill, not a discipline skill.

## Red Flags

- You drafted a letter referencing a personalization hook that came from your own background knowledge rather than the card, the light-pass enrichment, or the Phase 2 deeper intelligence.
- You wrote a letter that names a product, customer, metric, or date not in the contact's `verified_entities` list (which now includes Phase 2 findings).
- You skipped the naturalize pass for any draft. The naturalize pass is mandatory.
- You wrote the letters or the deeper intelligence to a separate file outside the card. Both outputs must be appended inside the card.
- You ran the copywriter or naturalizer in the background (writer agents must be foreground waves).
- You ran the enrichment subagents in the background (writer agents must be foreground waves).
- You exceeded 6 concurrent agent dispatches in a single wave (Phase 2 uses 5 subagents; that fits in one wave).
- You dispatched an enrichment subagent without first reading its existing-card-data block from `card_parsed.json`. Subagents must be told what is ALREADY known so they can hunt for gaps, not duplicate findings.
- You added a `## Outreach Letters` or `## Deeper Intelligence` section to the card without first removing the prior version (re-runs must replace, not duplicate).
- You modified the card's earlier sections (Overview, Key Contacts, Outreach Recommendation, etc.) — only the new `## Deeper Intelligence` + `## Outreach Letters` sections and their trailing footer lines are this skill's outputs.
- You wrote the rebuilt card back to `source_path` instead of `target_path = .mz/outreach/active/<today>_<company_slug>.md`. The card must end this run at the active path with today's date prefix.
- You preserved the source file at its research-baseline or stale-active location after Phase 5 completed (a successful run leaves exactly one card for the slug, at `target_path`).
- You left multiple active files for the same slug behind — only today's-dated file should remain.
- You discarded the `## Interaction History` section (if present below the prior `## Outreach Letters` section). Interaction history is owned by `/outreach-update-card` and must be preserved verbatim.

## Verification

Before emitting `STATUS: DONE`, confirm:

1. The card now lives at `target_path = .mz/outreach/active/<today>_<company_slug>.md`.
1. If `source_path != target_path`, the source file no longer exists.
1. `.mz/outreach/active/` contains exactly one file matching `*_<company_slug>.md`.
1. If `enrich_mode != "skip"`, the card at `target_path` contains a `## Deeper Intelligence` section with at least one populated subsection.
1. If `enrich_mode != "only"`, the card at `target_path` contains a `## Outreach Letters` section. Every non-skipped (contact, channel) pair produced one letter under that section. Each letter shows a `**Subject**:` line (email only) plus the body. The `## Naturalization report` block does NOT appear under any letter in the final card.
1. The card retains its original `*Generated: <date> | Sources: <list>*` footer above the new sections.
1. New footers sit at the bottom of each new section: `*Deeper intelligence: <date> | subagents: <N> | failed: <M>*` and `*Letters generated: <date> | naturalized: yes | light queries: <K> | reverted: <R>*`.
1. Section order on the card is: original sections → `## Deeper Intelligence` (if present) → `## Outreach Letters` (if present) → `## Interaction History` (if it existed before).

## Resume Support

Before creating anything in Phase 0, run Source Resolution to derive `company_slug` and `source_path`, then check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` and `SourcePath` fields and resume from the next incomplete phase:

- `Phase: 0` → restart from Phase 0 with freshly resolved `source_path` (do not trust the stored `SourcePath` since the prior run did not complete validation).
- `Phase: card_parsed` → resume from Phase 2 (or Phase 3 if `enrich_mode == "skip"`). Use the stored `SourcePath`.
- `Phase: enrichment_complete` → resume from Phase 3 (or jump to Phase 5 if `enrich_mode == "only"`). Use the stored `SourcePath`.
- `Phase: briefs_complete` → resume from Phase 3 drafting. Use the stored `SourcePath`.
- `Phase: drafts_complete` → resume from Phase 4. Use the stored `SourcePath`.
- `Phase: naturalize_complete` → resume from Phase 5. Use the stored `SourcePath` for the read; compute `target_path` fresh from today's date.
- `Phase: complete` → no work to do; emit verification block from state. If the freshly resolved `source_path` differs from state's `TargetPath` (e.g., user re-invoked on a stale path or a new day passed), treat it as a new run and restart from Phase 0 with a new `task_name` (`_v2`, `_v3`).

All phases are idempotent — re-running overwrites output files. Phase 5 writes to `target_path` (today's active path), replacing any prior file at that exact location; the post-write cleanup step removes the source if it differs.

## Error Handling

- User path missing or no source can be resolved (user path does not exist AND no matching active card found) → `STATUS: BLOCKED`. Surface the failing check.
- `strategy.json` missing → fall back to default sender voice; final STATUS becomes `DONE_WITH_CONCERNS`; the verification block names the absence.
- Light-pass cap hit (6 calls) → drop the lowest-priority queries; record the drop in `state.md` and the final footer.
- One enrichment subagent in Phase 2 returns `BLOCKED` or `NEEDS_CONTEXT` → continue the wave for other subagents; mark the corresponding subsection as `unavailable` in the `## Deeper Intelligence` block; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry.
- All five enrichment subagents fail → still emit the `## Deeper Intelligence` section with each subsection marked `unavailable: <reason>` so the failure is visible in the card; downgrade STATUS to `DONE_WITH_CONCERNS`.
- One `expert-copywriter` dispatch returns `BLOCKED` or `NEEDS_CONTEXT` → continue the wave for other contacts; mark this contact `failed_draft` in `state.md`; the contact appears as `### Skipped: <Name> — <reason>` under the card section; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry — the failure reason must surface to the user.
- One `expert-naturalizer` dispatch over-shortens a draft (post-validation finds word count outside channel budget by >5% or subject line drifted) → restore the pre-naturalize snapshot; mark `naturalize_reverted` in `state.md`; the pre-naturalize draft is what gets appended; final STATUS becomes `DONE_WITH_CONCERNS`.
- Card has no Key Contacts at all AND `enrich_mode != "only"` → `STATUS: BLOCKED` with message "card has no Key Contacts — re-run /outreach-research or hand-edit the card first, or run with enrich:only to skip letters."
- Any agent run more than once with `NEEDS_CONTEXT` → escalate via `AskUserQuestion` with the agent's stated missing piece. Otherwise no user prompts.
- Source-file deletion fails during Phase 5 cleanup (permission, file vanished, fs error) → do NOT fail the run; log `relocation_cleanup_failed: <reason>` in `state.md`; downgrade final STATUS to `DONE_WITH_CONCERNS`. The card content at `target_path` is canonical regardless; the user can clean up the stale source manually.
- `.mz/outreach/active/` is unwritable (permission, read-only mount) → `STATUS: BLOCKED`. The skill cannot complete without writing the activated card.
- Never fabricate contacts, hooks, news items, metrics, or any other content. Incomplete output is better than fabricated content.
