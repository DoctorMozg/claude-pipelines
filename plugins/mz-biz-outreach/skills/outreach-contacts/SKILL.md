---
name: outreach-contacts
description: ALWAYS invoke when the user wants to generate LinkedIn/email outreach letters from an existing company card .md created by outreach-research. Drafts one letter per Key Contact, naturalizes each, and appends the letters inside the card. Triggers - "write outreach letters for <card>", "draft messages from <card>", "generate letters for this company card", "outreach letters from <path>".
argument-hint: "<path/to/company_card.md>" [channels:email|linkedin|both] [sender:<voice text or path>]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Outreach Contacts

## Overview

You are an orchestrator that converts a company card produced by `/outreach-research` into ready-to-send outreach letters. Given the path to a `companies/<slug>.md` card, you parse the card, deepen the company knowledge with a short fresh web-research pass, draft one letter per named Key Contact via the `expert-copywriter` agent (channel auto-selected per contact), then mandatorily naturalize each draft via `expert-naturalizer` to strip AI-pattern residue. The final letters are appended directly inside the card as a new `## Outreach Letters` section, so the card becomes a self-contained outreach asset.

The whole pipeline is fully automatic — no approval gates, no mid-run prompts. The user invokes the skill, the skill writes letters, the card now holds them.

## When to Use

Invoke when the user has a company card (produced by `/outreach-research`, lives at `.mz/outreach/<run>/companies/<slug>.md`) and wants outreach letters drafted from it. Trigger phrases:

- "write outreach letters for `.mz/outreach/.../companies/<slug>.md`"
- "generate letters from this card"
- "draft LinkedIn/email outreach from `<path>`"
- "make outreach letters for `<company>`" (when a card already exists)

### When NOT to use

- The user has only a company name or domain and no card — run `/outreach-research` first (single-company mode if they want only one).
- The user wants to discover companies first — use `/outreach-research`.
- The user wants recruiter contacts for a job application — use `/job-recruiter-info` in mz-job-outreach.
- The user wants general marketing copy (landing pages, announcements, social) — use `/copywrite` from mz-creative.
- The user wants the letters written to a different location than the card — this skill only writes back into the card.

## Input

- `$ARGUMENTS` — Required: an absolute or repo-relative path to a company card `.md` file. Two accepted shapes:
  - **Research baseline**: `.mz/outreach/<run>/companies/<slug>.md` — direct output of `/outreach-research`. First activation moves it to `active/`.
  - **Active**: `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` — a card already activated by this skill or `/outreach-update-card`. The date prefix is the last interaction date; this run updates it to today.
- Optional modifiers (case-insensitive, order-independent):
  - `channels:email|linkedin|both` — overrides per-contact channel auto-detection. Default: best channel per contact (email if known, else LinkedIn DM, else skip).
  - `sender:<inline text or path>` — overrides the sender voice. Inline text becomes the voice description; a path is read as a sender bio markdown file. Default: read `<run>/strategy.json` `sender_voice` field if present.

If `$ARGUMENTS` is empty or no source can be resolved (see Source Resolution below), emit `STATUS: BLOCKED` with a clear message and stop.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **user_path** — the path token (everything not matching a parameter pattern). Must end in `.md`.
- **channels_override** — from `channels:<value>` (default: unset → per-contact auto-detect).
- **sender_override** — from `sender:<value>` (default: unset → use strategy.json or fallback voice).

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
- **Briefs** — `.mz/task/<task_name>/briefs/<contact_slug>.json`. One brief per contact selected for drafting.
- **Drafts** — `.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md`. One draft file per (contact, channel) pair. Each draft carries YAML frontmatter (`subject`, `channel`, `recipient`) followed by the body.
- **Card lifecycle** — the card ends this run at `target_path = .mz/outreach/active/<today>_<company_slug>.md`. If `source_path != target_path`, the source file is deleted in Phase 4 after the rewrite (move semantics). Research-baseline cards at `.mz/outreach/<run>/companies/<slug>.md` and stale-dated active cards (`active/<other-date>_<slug>.md`) are removed by this run.

`task_name` follows `<YYYY_MM_DD>_outreach_contacts_<company_slug>` where `<company_slug>` is derived in Source Resolution (slug without date prefix or `.md`). Same-day collisions append `_v2`, `_v3`.

`<run_dir>` = the directory containing `source_path` when the card is still at its research-baseline location (typically `.mz/outreach/<run>/companies/`). The sibling `strategy.json` lives at `<run_dir>/../strategy.json` — read it from there for sender voice and outreach angles. When `source_path` is already an active path, `<run_dir>` falls back to the most-recently-modified `.mz/outreach/<run>/` directory containing a `strategy.json` (or `default` voice if none can be located).

## Core Process

### Phase Overview

| #   | Phase                   | Agent(s)                              | Details                        |
| --- | ----------------------- | ------------------------------------- | ------------------------------ |
| 0   | Setup + card validation | — (orchestrator)                      | Inline below                   |
| 1   | Parse + web enrichment  | — (orchestrator + WebSearch/WebFetch) | Inline below                   |
| 2   | Draft letters           | `expert-copywriter`                   | `phases/draft_and_finalize.md` |
| 3   | Naturalize letters      | `expert-naturalizer`                  | `phases/draft_and_finalize.md` |
| 4   | Append to card          | — (orchestrator, Read + Write)        | `phases/draft_and_finalize.md` |
| 5   | Verification summary    | — (orchestrator)                      | Inline below                   |

Read `phases/draft_and_finalize.md` when you reach Phase 2.

### Phase 0: Setup + card validation

Parse arguments. Resolve `user_path`, `channels_override`, `sender_override`. Run Source Resolution (see Argument Parsing) to derive `company_slug` and `source_path`. Verify `source_path` exists and parses as a canonical company card.

Derive:

- `company_slug` — already set by Source Resolution (stripped of any date prefix and `.md`).
- `task_name` = `<YYYY_MM_DD>_outreach_contacts_<company_slug>` (truncate `<company_slug>` to 30 chars if needed). Collision: `_v2`, `_v3`.
- `task_dir` = `.mz/task/<task_name>/`.
- `run_dir` = if `source_path` is under `.mz/outreach/<run>/companies/`, then `dirname(dirname(source_path))`; otherwise (active path) the most-recently-modified `.mz/outreach/<run>/` directory that contains a `strategy.json`, falling back to `default` voice if none found.

```bash
mkdir -p .mz/task/<task_name>/briefs
mkdir -p .mz/task/<task_name>/drafts
mkdir -p .mz/outreach/active
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Outreach Contacts (Card Mode) State
- **Status**: running
- **Phase**: 0
- **Started**: <ISO timestamp>
- **UserPath**: <user-supplied path verbatim>
- **SourcePath**: <resolved path actually being read>
- **CompanySlug**: <slug>
- **RunDir**: <run_dir or "default">
- **ChannelsOverride**: <value or "auto">
- **SenderOverride**: <value or "strategy.json|default">
```

### Phase 1: Parse card + web enrichment

Read the card. Extract structured data — do this with normal markdown reading, not a regex parser. Capture:

- **Company**: name (from H1), domain, sector, location, founded, size, score (from the metadata header lines).
- **Overview**: the `## Overview` paragraph.
- **Key Contacts**: every numbered entry under `## Key Contacts`. Each entry is `**<Name>** — <Title> — [LinkedIn](<url>) — <relevance>`. Extract name, title, LinkedIn URL, relevance line. Also capture the trailing `**Emails**:`, `**Phone**:`, `**Company LinkedIn**:` lines. Cap at 5 contacts.
- **Recent News**: numbered entries under `## Recent News & Timing Signals`. Each: `**<Title>** (<date>, <category>, <timing_relevance> timing) — <outreach_implication>`. Keep top 3 by `timing_relevance` (high first).
- **Outreach Recommendation**: the synthesizing paragraph plus the three labeled lines `**Best contact**:`, `**Best angle**:`, `**Timing**:`.
- **Technology Profile**: stack list, maturity, GitHub URL, tech blog URL.
- **Growth Signals**: trajectory, open roles, funding (if present).
- **Red Flags**: any bulleted items (or "None identified").

Read `<run_dir>/strategy.json` if it exists. Capture the `sender_voice` (or `outreach_strategy.sender_voice`) and `outreach_angles` fields. If the file is missing OR the field is empty, use these defaults:

- `sender_voice` = `"Professional, concise, plain-spoken. No marketing register, no hype. First-person singular. Direct request, one CTA per letter."`
- `outreach_angles` = `["Value-first introduction citing one verified personalization signal from the card or fresh research."]`

If `sender_override` was supplied as an argument, it overrides the strategy.json value (inline text → used directly; path → read the file).

Record `strategy_source` per brief: `strategy.json` if loaded from disk, `default` if fallback applied, `sender_override` if argument was used. If `default`, the final STATUS will be `DONE_WITH_CONCERNS`.

#### Web enrichment

Run a single parallel wave of WebSearch/WebFetch calls. Hard cap: 10 calls per skill run. Priority order, drop the lowest priority first if the cap binds:

1. 1 × WebSearch — fresh company news (last 60 days). Query: `"<company name>" news 2026 OR recent` (adjust year to today's date).
1. 1 × WebSearch per Key Contact (up to 5) — public activity. Query: `"<contact full name>" "<company name>" linkedin OR podcast OR interview OR keynote`.
1. 1 × WebFetch — company tech blog URL if present in the card's Technology Profile.
1. 1 × WebFetch — company GitHub URL if present in the card's Technology Profile.
1. 1 × WebFetch — company X/Twitter handle if present anywhere in the card.
1. 1 × WebFetch per contact LinkedIn URL (best effort — LinkedIn often blocks unauthenticated fetches; treat any non-200 or empty body as a soft failure and fall back to the WebSearch result for that contact).

Run all chosen calls in a single message with multiple tool uses. Wait for the wave to complete. Capture per-contact and company-level signal strings (1–2 lines each, verbatim from the search snippet or fetched page title/H1/first paragraph). Discard anything that cannot be cited.

Record the total number of web calls actually issued — surface this in the Phase 4 footer and the Phase 5 verification block.

#### Build per-contact briefs

For each of the (up to 5) Key Contacts, decide the channel:

- If `channels_override == "email"` → channel = `email` (requires the contact's email to be known, else fall back to LinkedIn DM if URL known, else `skip`).
- If `channels_override == "linkedin"` → channel = `linkedin_dm` (requires LinkedIn URL, else `skip`).
- If `channels_override == "both"` → emit TWO briefs per contact when both handles exist: one `email`, one `linkedin_dm`. Skip a missing channel cleanly.
- If no override (default) → prefer `email` when an email is known; else `linkedin_dm` when LinkedIn URL is known; else `skip` and record the reason.

Per-channel handle resolution: the card lists contact emails in the `## Key Contacts` block's `**Emails**:` line — these are company-level (info@, sales@). Person-specific emails appear in the per-contact line only if the card found one. If only generic emails exist, mark the channel as `email_generic` and target the generic address with the contact named in the body.

For each non-skipped (contact, channel) pair, write `.mz/task/<task_name>/briefs/<channel>_<contact_slug>.json` (or `<contact_slug>.json` if a single channel per contact). Shape:

```json
{
  "company": {
    "name": "<from card>",
    "slug": "<company_slug>",
    "domain": "<from card>",
    "sector": "<from card>"
  },
  "recipient": {
    "name": "<full name>",
    "first_name": "<first name only>",
    "title": "<title from card>",
    "linkedin_url": "<url or null>",
    "email": "<email or null>",
    "relevance": "<relevance line from card>"
  },
  "chosen_channel": "email | email_generic | linkedin_dm",
  "channel_constraints": {
    "subject_max_chars": 55,
    "body_word_min": 120,
    "body_word_max": 180
  },
  "chosen_angle": "<one line from outreach_angles, picked to fit this contact>",
  "value_claim": "<one short sentence — the user-facing benefit, derived from strategy.outreach_angles + card outreach_recommendation>",
  "company_hook": "<one line from the card's Outreach Recommendation Best angle, paraphrased to fit this contact>",
  "personalization_hooks": [
    {
      "signal": "<verbatim signal from the card or web research>",
      "source": "card | web",
      "source_detail": "<which card section, or which URL>",
      "verified": true
    }
  ],
  "card_recent_news": [
    {
      "title": "<news title>",
      "date": "<date>",
      "outreach_implication": "<implication line from card>"
    }
  ],
  "verified_entities": [
    "<every proper noun, product name, metric, date, URL the copywriter is allowed to reference — populated from card + web enrichment only>"
  ],
  "strategy_source": "strategy.json | default | sender_override",
  "sender_voice": "<3–5 line voice description>",
  "channel_format_rules": "<copied verbatim from the channel rules table in phases/draft_and_finalize.md so the copywriter sees them inline>"
}
```

`channel_constraints` for `linkedin_dm`: `{ "subject_max_chars": 0, "body_word_min": 60, "body_word_max": 100 }`. For `email_generic`: same as `email` plus a `body_must_name_recipient: true` flag so the copywriter addresses the contact in the body even though the To: is generic.

Update `state.md` Phase field to `briefs_complete`, append a `Briefs` list (one path per file).

After all briefs are written, hand off to `phases/draft_and_finalize.md` for Phases 2–4.

### Phase 5: Verification summary

After Phase 4 completes, emit a visible block:

```
Outreach letters generated.
Source (read from): <source_path>
Card (final):       <target_path = .mz/outreach/active/<today>_<slug>.md>
Relocated:          <yes | no>     # yes if source_path != target_path
Task dir:           .mz/task/<task_name>/
Contacts drafted:    <N>   (channels: <breakdown>)
Contacts skipped:    <M>   (no contact route)
Enrichment queries:  <K>   (cap 10)
Naturalize reverted: <R>   (drafts where naturalize was rolled back)
Strategy source:     <strategy.json | default | sender_override>
STATUS: <DONE | DONE_WITH_CONCERNS>
```

`STATUS: DONE_WITH_CONCERNS` whenever any of: `strategy_source == default`, any contact was skipped, any draft was naturalize-reverted, any copywriter dispatch failed, any web call returned an error, the enrichment cap was hit and contacts had to drop, the relocation failed to delete the source file.

## Techniques

Techniques: delegated to `phases/draft_and_finalize.md`.

## Common Rationalizations

N/A — orchestration skill, not a discipline skill.

## Red Flags

- You drafted a letter referencing a personalization hook that came from your own background knowledge rather than the card or the web-enrichment pass.
- You wrote a letter that names a product, customer, metric, or date not in the contact's `verified_entities` list.
- You skipped the naturalize pass for any draft. The naturalize pass is mandatory.
- You wrote the letters to a separate file outside the card (e.g., a new report under `.mz/reports/`). Letters must be appended inside the card.
- You ran the copywriter or naturalizer in the background (writer agents must be foreground waves).
- You exceeded 6 concurrent agent dispatches in a single wave.
- You added a `## Outreach Letters` section to the card without first removing the prior version (re-runs must replace, not duplicate).
- You modified the card's earlier sections (Overview, Key Contacts, Outreach Recommendation, etc.) — only the new `## Outreach Letters` section and the trailing `*Letters generated:` footer are this skill's outputs.
- You wrote the rebuilt card back to `source_path` instead of `target_path = .mz/outreach/active/<today>_<company_slug>.md`. The card must end this run at the active path with today's date prefix.
- You preserved the source file at its research-baseline or stale-active location after Phase 4 completed (a successful run leaves exactly one card for the slug, at `target_path`).
- You left multiple active files for the same slug behind (e.g., `2026-05-12_acme.md` AND `2026-05-15_acme.md`) — only the today's-dated file should remain.
- You discarded the `## Interaction History` section (if present below the prior `## Outreach Letters` section). Interaction history is owned by `/outreach-update-card` and must be preserved verbatim.

## Verification

Before emitting `STATUS: DONE`, confirm:

1. The card now lives at `target_path = .mz/outreach/active/<today>_<company_slug>.md`.
1. If `source_path != target_path`, the source file no longer exists.
1. `.mz/outreach/active/` contains exactly one file matching `*_<company_slug>.md`.
1. The card at `target_path` contains a `## Outreach Letters` section.
1. Every non-skipped (contact, channel) pair produced one letter under that section.
1. Each letter shows a `**Subject**:` line (email only) plus the body.
1. The `## Naturalization report` block does NOT appear under any letter in the final card.
1. The card retains its original `*Generated: <date> | Sources: <list>*` footer above the new section.
1. A new `*Letters generated: <date> | naturalized: yes | enrichment queries: <N> | reverted: <R>*` footer sits at the very bottom of the card.

## Resume Support

Before creating anything in Phase 0, run Source Resolution to derive `company_slug` and `source_path`, then check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` and `SourcePath` fields and resume from the next incomplete phase:

- `Phase: 0` → restart from Phase 0 with freshly resolved `source_path` (do not trust the stored `SourcePath` since the prior run did not complete validation).
- `Phase: briefs_complete` → resume from Phase 2. Use the stored `SourcePath` from state.md (briefs were built against that file).
- `Phase: drafts_complete` → resume from Phase 3. Use the stored `SourcePath`.
- `Phase: naturalize_complete` → resume from Phase 4. Use the stored `SourcePath` for the read; compute `target_path` fresh from today's date.
- `Phase: complete` → no work to do; emit verification block from state. If the freshly resolved `source_path` differs from state's `TargetPath` (e.g., user re-invoked on a stale path or a new day passed), treat it as a new run and restart from Phase 0 with a new `task_name` (`_v2`, `_v3`).

All phases are idempotent — re-running overwrites output files. Phase 4.3 writes to `target_path` (today's active path), replacing any prior file at that exact location; Phase 4.4 removes the source if it differs.

## Error Handling

- User path missing or no source can be resolved (user path does not exist AND no matching active card found) → `STATUS: BLOCKED`. Surface the failing check.
- `strategy.json` missing → fall back to default sender voice; final STATUS becomes `DONE_WITH_CONCERNS`; the verification block names the absence.
- Web enrichment cap hit (10 calls) → drop the lowest-priority queries; record the drop in `state.md` and the Phase 4 footer.
- One `expert-copywriter` dispatch returns `BLOCKED` or `NEEDS_CONTEXT` → continue the wave for other contacts; mark this contact `failed_draft` in `state.md`; the contact appears as `### Skipped: <Name> — <reason>` under the card section; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry — the failure reason must surface to the user.
- One `expert-naturalizer` dispatch over-shortens a draft (post-validation finds word count outside channel budget by >5% or subject line drifted) → restore the pre-naturalize snapshot; mark `naturalize_reverted` in `state.md`; the pre-naturalize draft is what gets appended; final STATUS becomes `DONE_WITH_CONCERNS`.
- Card has no Key Contacts at all → `STATUS: BLOCKED` with message "card has no Key Contacts — re-run /outreach-research or hand-edit the card first."
- Any agent run more than once with `NEEDS_CONTEXT` → escalate via `AskUserQuestion` with the agent's stated missing piece. Otherwise no user prompts.
- Source-file deletion fails during Phase 4.4 (permission, file vanished, fs error) → do NOT fail the run; log `relocation_cleanup_failed: <reason>` in `state.md`; downgrade final STATUS to `DONE_WITH_CONCERNS`. The card content at `target_path` is canonical regardless; the user can clean up the stale source manually.
- `.mz/outreach/active/` is unwritable (permission, read-only mount) → `STATUS: BLOCKED`. The skill cannot complete without writing the activated card.
- Never fabricate contacts, hooks, news items, metrics, or any other content. Incomplete letters are better than fabricated ones.
