# Phase 2: Deep Enrichment via Subagents

Read `SKILL.md` first. This file picks up after Phase 1 (`card_parsed.json` written under `.mz/task/<task_name>/`) and runs Phase 2.

Skip this entire file if `enrich_mode == "skip"`.

## Purpose

The base `/outreach-research` skill produced the card. Its enrichment phase ran each specialist agent once. This phase re-runs the same five specialists with **explicit gap-filling intent** — each agent receives the existing-findings block from the card and is instructed to surface only NEW information, going deeper on specifics the base research left thin or stale.

## 2.1 Build the existing-findings payload

Read `.mz/task/<task_name>/card_parsed.json` (written in Phase 1). From it, derive a compact per-agent "what is already known" block. Each agent gets a different slice — only the parts of the card it must NOT duplicate.

```json
// existing_findings shape (computed in-memory, not written to disk)
{
  "news":   { "items": [ <recent_news verbatim> ] },
  "tech":   { "stack": <tech_profile.stack>, "github_url": <tech_profile.github_url>, "tech_blog_url": <tech_profile.tech_blog_url>, "maturity": <tech_profile.maturity> },
  "growth": { "trajectory": <growth_signals.trajectory>, "open_roles": <growth_signals.open_roles>, "funding": <growth_signals.funding>, "size": <company.size>, "founded": <company.founded> },
  "scanner":  { "review_summary": "<one-line summary of existing review/score data from the card overview, if any>" },
  "contacts": { "key_contacts": [ <key_contacts verbatim with name/title/linkedin/email>] }
}
```

If a field is missing in the card, pass `null` — that subagent then has wide-open territory to research.

## 2.2 Dispatch plan (single wave, 5 agents in parallel)

Dispatch all five subagents in **one parallel wave** via the Agent tool. The cap is 6 concurrent agents per wave; five fits cleanly in one. Foreground only — these agents write artifact files, so they must run in the foreground.

| Subagent                  | Output path                                       | Existing-findings slice |
| ------------------------- | ------------------------------------------------- | ----------------------- |
| `outreach-news-finder`    | `.mz/task/<task_name>/enrichment/news.json`       | `news`                  |
| `outreach-tech-analyst`   | `.mz/task/<task_name>/enrichment/tech.json`       | `tech`                  |
| `outreach-growth-analyst` | `.mz/task/<task_name>/enrichment/growth.json`     | `growth`                |
| `outreach-scanner`        | `.mz/task/<task_name>/enrichment/reputation.json` | `scanner`               |
| `outreach-contact-finder` | `.mz/task/<task_name>/enrichment/contacts.json`   | `contacts`              |

## 2.3 Dispatch template (one Agent call per subagent, all 5 sent in a single message)

Use `subagent_type: <agent name>`. Dispatch prompt skeleton (adapt the per-agent verbs and the existing-findings slice):

````
Role: deep-enrichment pass for a single company.

Company context:
  name: <company.name>
  slug: <company.slug>
  domain: <company.domain>
  sector: <company.sector>
  location: <company.location>

Output path: .mz/task/<task_name>/enrichment/<artifact>.json
  (use exactly this path; do not write anywhere else)

Existing findings ALREADY documented in the company card (do NOT duplicate
these; treat them as ground truth and look for gaps, deeper specifics, more
recent data, or contradicting evidence):

<paste the relevant slice of existing_findings JSON here, verbatim,
inside a fenced ```json block>

Your job for this pass is to GO DEEPER than the base research. Specifically:
  <see per-agent "depth directives" below — paste only the relevant block>

Hard rules:
  - Do not re-report items already present in the existing findings block
    above unless you have strictly more specific or more recent data
    (newer date, exact figure, named source). When you do, flag the entry
    with `"supersedes_existing": true` in the JSON.
  - Every fact must be grounded in a source the agent's source-discipline
    rules permit. Mark anything you cannot verify with `verified: false`.
  - If a category is empty after honest research, return an empty list and
    say so in your STATUS line — do not pad.
  - Cap your output at 10 items per category. Pick the most actionable.

Output format: the JSON shape this agent's own README defines (news.json /
tech.json / growth.json / reputation.json / contacts.json). Add one top-level
field `gap_fill_notes` (1–3 sentences) describing what NEW ground this pass
covered relative to the existing findings.

Return STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED.
````

### Per-agent depth directives

Paste only the matching block into each agent's dispatch.

**`outreach-news-finder` depth directives:**

```
- Find news items from the last 60 days that are not in existing findings.
- Look for: customer wins, partnership signings, product launches not yet
  on the changelog, executive appearances at conferences (named talks),
  open-source releases, press from non-English sources if the company
  operates internationally.
- For each item, fill `outreach_implication` with a one-line read on how
  this affects an outbound conversation NOW.
```

**`outreach-tech-analyst` depth directives:**

```
- Identify specific frameworks, libraries, vendors, or cloud regions
  beyond the high-level stack list already in the card.
- Look at recent job postings (last 60 days) for new tech requirements
  the base research missed.
- Audit GitHub org for: recent active repos (<90 days), open-source
  releases under the company name, named maintainers from the company,
  language distribution.
- Audit the engineering blog (if present) for: the 3 most recent posts,
  their authors, and what technical decisions they hint at.
- Flag any signals of: migration in progress, scaling pain, hiring for
  a new area, vendor switch.
```

**`outreach-growth-analyst` depth directives:**

```
- Beyond headcount/funding already listed, look for: LinkedIn employee
  count delta vs 6 months ago, named recent senior hires (Director+),
  recent departures or org-restructure signals, geographic expansion
  beyond the recorded HQ, new office openings.
- Quote at least one numeric signal verbatim (open role count, headcount
  range, funding stage round-size) sourced to a dated page.
- Surface any tension signal: hiring freeze, layoffs, profit-warning,
  pivot announcement, leadership churn.
```

**`outreach-scanner` depth directives:**

```
- Beyond a single aggregate score, capture per-platform breakdowns:
  Glassdoor rating + sample employee comment themes (one line),
  Trustpilot rating + sample customer comment themes (one line),
  G2/Capterra if relevant + buyer themes, Google Business if local.
- Pull the 3 most recent reviews (titles + dates only, no body) per
  platform so they can be cited.
- Flag any sentiment trend: improving, deteriorating, polarized,
  steady. Cite the time window you compared.
```

**`outreach-contact-finder` depth directives:**

```
- Beyond the named contacts already in the card, find:
  (a) one additional named decision-maker per relevant function (eng,
      product, marketing, sales, founder/CEO) NOT already listed;
  (b) per-contact public-activity signals (recent post, talk, GitHub
      contribution, podcast) that could seed personalization;
  (c) generic role-based contact patterns the card lacks
      (careers@, partnerships@, security@, press@) — verified by visiting
      the company site, not guessed.
- Do NOT re-emit the contacts already in the card. Only ADD.
- For each new contact, mark `is_addition: true`.
```

## 2.4 Validate each subagent result

After the wave returns, for each of the five outputs:

1. Verify the file exists at the expected path (`enrichment/<artifact>.json`) and parses as JSON. If the file is missing, the agent never wrote — mark `failed: missing_artifact`.
1. Verify the agent's terminal `STATUS:` line. Map: `DONE` → ok; `DONE_WITH_CONCERNS` → ok-with-note; `NEEDS_CONTEXT`/`BLOCKED` → failed.
1. Verify the JSON has the expected top-level shape for that agent. If a category is empty AND the agent reported `DONE`, that means the gap-fill came up empty — record it as ok-with-empty, not failed.
1. Verify the `gap_fill_notes` field exists. Missing → ok-with-note (the data is still usable, just unannotated).

If 3 or more subagents failed, the section will still be emitted (per `SKILL.md` Error Handling) but with `unavailable: <reason>` rows; downgrade the final STATUS to `DONE_WITH_CONCERNS`.

Do NOT auto-retry. If the user wants another pass, they re-invoke the skill (resume support picks up at `Phase: card_parsed` and re-dispatches Phase 2).

## 2.5 Synthesize the `## Deeper Intelligence` section

Compose a markdown block from the merged enrichment artifacts. Write it to `.mz/task/<task_name>/deeper_intelligence.md` (consumed by Phase 5 during card rewrite). Layout:

```markdown
## Deeper Intelligence

*Gap-fill pass on top of the base research. Five specialist subagents were dispatched in parallel; their findings are de-duplicated against the original card.*

### Recent News (deeper pass)

<from enrichment/news.json — list each `items[]` entry as a bullet:
"- **<title>** (<date>, <category>) — <outreach_implication>. Source: <url>.">
<if supersedes_existing: true, prefix with "↑ supersedes existing: ">

*gap_fill_notes:* <verbatim from news.json>

OR (if the subagent failed or returned empty):

*unavailable — <reason>* | *no new news beyond the base research*

### Technology (deeper pass)

<from enrichment/tech.json — summarize per category: new stack items,
recent GitHub repos, recent eng-blog authors, scaling/migration signals.
One bullet per finding, cite source URL.>

*gap_fill_notes:* <verbatim>

### Growth Signals (deeper pass)

<from enrichment/growth.json — bullet list with at least one verbatim
numeric quote.>

*gap_fill_notes:* <verbatim>

### Reputation (deeper pass)

<from enrichment/reputation.json — per-platform sub-bullets:
- **Glassdoor**: <score> — <one-line theme>. Recent reviews: <list>.
- **Trustpilot**: ...
- **G2/Capterra**: ...
- **Google Business**: ...
Sentiment trend: <improving|deteriorating|polarized|steady> over <window>.>

*gap_fill_notes:* <verbatim>

### Additional Contacts (deeper pass)

<from enrichment/contacts.json — list ONLY contacts with is_addition: true.
Format same as the card's Key Contacts section. Also list any generic
role-based contacts found (careers@, partnerships@, etc.).>

*gap_fill_notes:* <verbatim>

*Deeper intelligence: <today's date> | subagents: <N_dispatched> | failed: <M_failed>*
```

If a category is `unavailable`, still emit the heading so the user can see the failure surface — just leave the body as the `*unavailable — <reason>*` line.

If `enrich_mode == "only"`, the deeper-intel personalization signals do NOT flow into letter briefs (since no letters are drafted). If `enrich_mode == "both"` (default), Phase 3 brief-building reads `deeper_intelligence.md` plus the raw `enrichment/*.json` files and pushes any high-signal facts into the per-contact `verified_entities` and `personalization_hooks` arrays.

## 2.6 Update state and hand off

Update `.mz/task/<task_name>/state.md`:

- Phase → `enrichment_complete`
- Append `EnrichmentResults` list, one row per subagent: `<agent_name>: <ok|ok-with-empty|failed:<reason>>`.
- Append `DeeperIntelArtifact: .mz/task/<task_name>/deeper_intelligence.md`.

If `enrich_mode == "only"`, jump directly to Phase 5 (`phases/draft_and_finalize.md` Phase 5 — card rewrite only). Otherwise advance to Phase 3 (drafting in the same file).

## Brief-building integration (read by Phase 3)

When `phases/draft_and_finalize.md` runs Phase 3 brief-building (which currently reads only `card_parsed.json`-style structure from Phase 1), it must ALSO consume `enrichment/*.json` so deeper-intel facts become eligible personalization signals.

For each contact's `briefs/<channel>_<contact_slug>.json`:

- Extend `verified_entities` with every proper noun, product name, metric, date, and URL surfaced by the deeper-intel pass that the agent did not flag `verified: false`.
- Extend `personalization_hooks` with any per-contact public-activity signal returned by `outreach-contact-finder` (`is_addition: false` entries that added activity signals for an existing contact, or `is_addition: true` entries if that NEW contact is also being drafted to).
- Tag each new hook with `source: "deeper_intel"` and the originating subagent in `source_detail` (e.g. `"news.json: <title>"`).

This integration is the only place Phase 2 output flows into Phase 3. The card-side rendering happens in Phase 5.

## Red Flags

- You dispatched the subagents without the existing-findings block — they re-report what's already in the card.
- You wrote a subagent artifact to a path other than `enrichment/<agent_slug>.json`.
- You merged subagent output into the card directly (skipping `deeper_intelligence.md`) — Phase 5 owns the card-rewrite.
- You skipped one of the five subagents without reason. The full five-agent fan-out is the contract.
- You ran the agents sequentially when they're independent. Single parallel wave only.
- You auto-retried a `BLOCKED`/`NEEDS_CONTEXT` subagent. Failures surface to the user via the verification block; no silent retry.
