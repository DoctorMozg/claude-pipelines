---
name: freelance-search
description: ALWAYS invoke when the user wants to find freelance gigs, contracts, or consulting engagements matched to a CV from vetted/niche/regional boards (not Upwork/Fiverr). Triggers: "find freelance gigs", "freelance search", "freelance hunt".
argument-hint: "<free-text preferences>" [limit:N] [recency:Nd] [pitches:topN]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Freelance Search Pipeline

## Overview

You are an orchestrator for a CV-to-gigs freelance pipeline. Given a CV and a free-text preferences prompt, you collect region scope, build a freelance strategy (discipline + three-format rate floor + engagement-type filter), assemble sources from the freelance canonical list plus researcher augmentations, scout multiple vetted/regional/niche boards in parallel, normalize and filter gigs against engagement-type and region, score each gig on a freelance-specific weighted axis model, and produce a single ranked report with top-N scored gigs plus DOC-ONLY guidance cards for referral-only networks.

Output is a master markdown report. Proposals are not generated here — use `/freelance-pitch <rank or URL>` to generate a proposal for a selected gig.

This skill explicitly excludes mass-market open marketplaces (Upwork, Fiverr, PeoplePerHour, Freelancer.com, Guru) — a user-locked exclusion enforced by the source-researcher's freelance-mode blocklist.

## When to Use

Invoke when the user wants to discover freelance/contract/consulting work matching their CV, build a gig shortlist, or prepare for outreach to vetted freelance networks. Trigger phrases: "find freelance gigs", "freelance hunt", "find contract work", "match contracts to my CV", "find consulting engagements".

### When NOT to use

- The user wants salaried roles — use `/job-search` instead.
- The user wants to draft a proposal for a single known gig — use `/freelance-pitch` instead.
- The user explicitly wants Upwork/Fiverr postings — this skill blocks them; redirect the user.
- The user wants fractional/retainer arrangements — this skill scopes to project gigs, contractor placements, and consulting/advisory only.
- The user has not provided a CV — the pipeline asks for one before invoking.

## Input

- `$ARGUMENTS` — free-text preferences body. Examples:
  - `"Senior backend freelance, Go/Rust, prefer DACH/EU, day rate €700+, project or contract"`
  - `"UX consulting, $200/hr floor, US-based clients, advisory only"`
  - `"Frontend contract React/TS, 6+ months, remote EMEA, $80/hr+"`
- **CV path** — collected interactively in Phase 0.
- **Region scope** — collected interactively in Phase 0 via AskUserQuestion (`Global`, `EU`, `US`, `DACH`, `UK`, `France`, `CV-driven`).

If `$ARGUMENTS` is empty, ask the user what kind of gigs they want and what constraints matter (discipline, engagement type, rate floor, region) before invoking.

## Scope Parameters

Extract scope modifiers from `$ARGUMENTS`, case-insensitive. Remaining text is the free-text preferences body.

- **`limit:<N>`** — maximum gigs carried through the pipeline. Default: 40.
- **`recency:<N>d`** — only keep gigs posted in the last N days. Default: 30 (freelance gigs are slower-moving than salaried).
- **`pitches:top<N>`** — convenience flag the user can pass to indicate they want this many top gigs surfaced for `/freelance-pitch` use. Not enforced here; informational only. Default: 5.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **preferences** — full free-text body (everything not matching a parameter pattern).
- **limit** — optional, from `limit:<N>` (default: 40).
- **recency_days** — optional, from `recency:<N>d` (default: 30).
- **pitches_top_n** — optional, from `pitches:top<N>` (default: 5).

## Directory Structure

Two separate directories are used:

- **State** — `.mz/task/<task_name>/state.md`. Source of truth across phases.
- **Outreach data** — `.mz/outreach/<run_name>/` holds `search_strategy.json`, `sources.json`, temp `_scout/`, `raw_gigs.json`, `scored.json`, `scored_excluded.json`, and the final `<YYYY_MM_DD>_freelance_search_<slug>.md` report.

`task_name` follows the pattern `<YYYY_MM_DD>_freelance_search_<slug>`; `run_name` is `<YYYY_MM_DD>_freelance_search_<preferences_slug>`. Same-day collisions append `_v2`, `_v3`.

## Core Process

### Phase Overview

| #   | Phase                             | Agent(s)                                              | Details                          |
| --- | --------------------------------- | ----------------------------------------------------- | -------------------------------- |
| 0   | Setup, CV collection, region pick | — (orchestrator, AskUserQuestion)                     | Inline below                     |
| 1   | Strategy                          | `freelance-strategist`                                | `phases/strategy_and_sources.md` |
| 1.5 | User approval of strategy         | — (orchestrator, AskUserQuestion)                     | Inline below                     |
| 2   | Source assembly                   | `job-source-researcher` mode=freelance (+ canonical)  | `phases/strategy_and_sources.md` |
| 3   | Scout fan-out                     | N × `freelance-scout` (parallel, skips guidance-only) | `phases/scout_score_report.md`   |
| 4   | Normalize + filter                | — (orchestrator, inline)                              | `phases/scout_score_report.md`   |
| 4.5 | Cheap pre-score (LLM 0/1/2)       | N × `job-prescorer` (reused, format-agnostic)         | `phases/scout_score_report.md`   |
| 5   | Full score & rank                 | N × `freelance-scorer` (parallel)                     | `phases/scout_score_report.md`   |
| 6   | Master report + guidance cards    | — (orchestrator, inline)                              | `phases/scout_score_report.md`   |

Read each phase file only when you reach the phase it covers.

### Strategy schema (Phase 1 output)

`search_strategy.json` carries the freelance-mode contract every downstream agent reads. Key fields specific to freelance mode:

- **`derived_from_cv.discipline`** — primary discipline detected from CV (one of `engineering`, `design`, `marketing`, `product`, `data`, `ops`, `founder`).
- **`derived_from_cv.secondary_disciplines`** — up to 2 secondary disciplines.
- **`preferences.engagement_types`** — subset of `["project_gig", "contractor_placement", "consulting_advisory"]`. `fractional_retainer` is forbidden by user-locked exclusion.
- **`preferences.regions_allowed`** — derived from runtime `region_scope` plus user-stated regions.
- **`rate_floor`** — three formats: `hourly_usd`, `daily_usd`, `project_total_usd` + `fx_basis` + `normalization_notes`.
- **`scoring_weights`** — sum=100 across seven freelance-specific axes (skill_match=40, location_eligibility=15, scope_clarity=10, budget_fit=10, client_vetting_presence=10, recency=10, discipline_fit=5).

Legacy fields shared with job-search (`search_queries`, `title_aliases`, `bilingual_query_variants`, `must_have_skills`, `nice_to_have_skills`, `location_eligibility_rule`, `recency_window_days`, `notes`) remain in place.

### Phase 1.5: User Approval of Strategy

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. Interactive — must not be delegated.

**Mandatory pre-read**: Read `.mz/outreach/<run_name>/search_strategy.json` with the Read tool. Capture the full file contents into context. The strategy file is JSON — present it verbatim inside a fenced \`\`\`json block.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `search_strategy.json` inside a fenced \`\`\`json block. Never substitute a path, summary, or one-line description.

Before invoking AskUserQuestion, emit a text block:

```
**Freelance-search strategy ready for review**
Built from your CV plus preferences and selected region. Derived discipline, engagement types, rate floor (in all three formats), region eligibility, and scoring weights are below. Approve to start scouting.

- **Approve** → proceed to Phase 2 (source assembly + scout)
- **Reject** → task marked aborted, no scouting runs
- **Feedback** → re-run strategy with your input, loop back here for re-review
```

Invoke AskUserQuestion with this body (where `<verbatim search_strategy.json contents>` is replaced by the bytes you just read):

````
Freelance-search strategy drafted from CV + preferences. Please review before scout dispatch:

```json
<verbatim search_strategy.json contents>
```

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
````

**Response handling**:

- **"approve"** → update `state.md` `Phase` to `strategy_approved`, proceed to Phase 2.
- **"reject"** → update `state.md` `Status` to `aborted_by_user` and stop.
- **Feedback** → re-dispatch `freelance-strategist` with feedback appended, overwrite `search_strategy.json`, return to this gate, re-read, and re-present via AskUserQuestion with full new contents inside the fenced json block. Loop until explicit approval.

## Techniques

Delegated to phase files — see Phase Overview table.

## Common Rationalizations

N/A — orchestration skill.

## Red Flags

- You dispatched scouts before the user approved the strategy.
- You included a banned source (Upwork, Fiverr, PeoplePerHour, Freelancer.com, Guru) — the researcher should block these in freelance mode; if a scout receives one, halt and report a bug.
- Master report lives in chat instead of `.mz/outreach/<run_name>/<YYYY_MM_DD>_freelance_search_<slug>.md`.
- A gig was scored against the job-mode axis list instead of the freelance axis list.
- `rate_floor` was missing from strategy but the scorer was dispatched without redistributing the `budget_fit` weight.
- Guidance-only entries (`scrape_allowed: false`) were scraped instead of rendered as DOC-ONLY cards in the report.

## Verification

Before completing, output a visible block showing: run name, total gigs scraped, gigs excluded by engagement-type or region filter, total ranked, top-1 final score, count of guidance-only sources rendered as cards, and the absolute path of the master report. Confirm the report file, scored JSON, and any guidance-card sections all exist on disk.

______________________________________________________________________

## Phase 0: Setup, CV collection, region pick

Parse arguments. Derive:

- `task_name` (state dir) = `<YYYY_MM_DD>_freelance_search_<slug>`, slug is snake_case preferences summary (max 20 chars).
- `run_name` (outreach dir) = `<YYYY_MM_DD>_freelance_search_<preferences_slug>`, max 40 chars.

```bash
mkdir -p .mz/task/<task_name>
mkdir -p .mz/outreach/<run_name>
mkdir -p .mz/outreach/_history
```

### CV collection

Invoke `AskUserQuestion` to collect the CV path. Acceptable: `.md`, `.txt`.

Pre-gate block:

```
**CV path needed**
The skill needs a path to your CV in markdown or plain text. PDF and DOCX are not supported — convert first if needed.

- Provide an absolute or relative path to your `.md` or `.txt` CV
```

AskUserQuestion body:

```
What is the path to your CV file? Provide an absolute or relative path to a `.md` or `.txt` file. Type your answer or **Cancel** to abort.
```

Validation:

1. "Cancel" → `Status: aborted_by_user`, stop.
1. File missing or wrong extension → re-ask once; second failure → `Status: aborted_missing_cv`, stop.
1. Success → read CV, capture absolute path.

### Region scope pick

Invoke `AskUserQuestion` to collect the region scope. Pre-gate block:

```
**Region scope needed**
Which region should we scope the freelance search to? Affects which boards we prioritize (Malt for EU, YunoJuno for UK, freelance.de for DACH, etc.) and which gigs we keep after the location-eligibility filter.

- **Global** — any region; widest net
- **EU** — EU-wide remote and on-site
- **US** — US-wide remote and on-site
- **DACH** — Germany, Austria, Switzerland
- **UK** — United Kingdom
- **France** — France-specific (Malt-heavy)
- **CV-driven** — derive from CV's current_location
```

AskUserQuestion options (single-select): `Global`, `EU`, `US`, `DACH`, `UK`, `France`, `CV-driven`.

Capture the selection as `region_scope`.

### CV-hash computation (for yield history)

```bash
cv_hash=$(tr '[:upper:]' '[:lower:]' < "<CV_PATH>" | tr -s '[:space:]' ' ' | sha1sum | cut -c 1-40)
```

### State file

Write `.mz/task/<task_name>/state.md`:

```yaml
schema_version: 2
Status: running
Phase: 0
Started: <ISO timestamp>
phase_complete: false
what_remains: []
Preferences: <free-text body>
CV path: <abs path>
CV hash: <cv_hash>
Region scope: <region_scope>
Limit: 40
RecencyDays: 30
PitchesTopN: 5
RunName: <run_name>
```

After setup, read `phases/strategy_and_sources.md` and proceed to Phase 1.

______________________________________________________________________

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

______________________________________________________________________

## Resume Support

Before creating anything in Phase 0, check if `.mz/task/<task_name>/state.md` exists. If it does, read `Phase` and resume from the next incomplete phase. All phases are idempotent.

## Error Handling

- Agent fails or returns empty: append `Errors:` bullet in `state.md`, continue with available data.
- ALL agents in a phase fail (zero results): stop the pipeline, report the failure.
- Never fabricate data.
- An agent returns `STATUS: NEEDS_CONTEXT`: invoke `AskUserQuestion` to fill the gap, re-dispatch.
