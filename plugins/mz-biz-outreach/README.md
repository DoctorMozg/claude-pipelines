# mz-biz-outreach

Autonomous business-outreach pipelines for Claude Code. Four complementary skills work on a shared card lifecycle: `/outreach-brief` **captures an outreach brief** (iterative clarification loop) and **researches the local business climate** of each target market; `/outreach-research` **discovers companies** and produces dossier cards; `/outreach-enrich-company` **deepens a card** via 5 specialist subagents and drafts naturalized LinkedIn/email letters inside it; `/outreach-update-card` **logs dated interaction entries** at the bottom of the card. The brief and climate feed `/outreach-research` and `/outreach-enrich-company` via a `brief:` argument. Both writer skills relocate the card to `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` (last-interaction-date prefix).

> Looking for job-hunting tools (`/job-search`, `/job-recruiter-info`)? Those moved to a dedicated plugin: **`mz-job-outreach`**.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-biz-outreach
```

## Skills

### `/outreach-brief` — Outreach Brief + Local-Climate Research

Front of the funnel. First runs an **iterative clarification loop** to capture a complete outreach brief — offering and value prop, ideal customer profile, target geography, and goal/channels/voice — asking until every required dimension is clear (it never guesses). Then it researches the **local business climate** for each target industry × region (capped at 20 combos): a source-discovery wave followed by a climate-research wave surface economic & market trends, regulatory & policy shifts, industry deals & news, and sector pain points within the last 12 months, plus ready-to-use proposal hooks.

```
/outreach-brief
/outreach-brief DevOps consulting for mid-size manufacturers in Bavaria
```

Outputs `brief.json` / `brief.md` and `climate.json` / `climate.md` into `.mz/outreach/<run>/`, then stops. One approval gate on the assembled brief precedes the research. Pass the run to the downstream skills with `brief:<run_name>` to ground their strategy and proposals in the local climate:

```
/outreach-research brief:<run_name>
/outreach-enrich-company <card> brief:<run_name>
```

### `/outreach-research` — Outreach Research Pipeline

Full autonomous outreach intelligence. Takes a target description and runs an 8-phase pipeline: defines strategy, researches sources, discovers companies, scans reputations, enriches with contacts/news/growth/tech data, scores leads, writes per-company dossier cards, and produces an executive summary.

```
/outreach-research find potential clients for our DevOps consulting in DACH region
/outreach-research SaaS companies in Latin America sector:HR-tech limit:30
/outreach-research find AI startups in Singapore for partnership opportunities
```

**Parameters**:

- `sector:<filter>` — narrow by industry (default: inferred by strategist)
- `limit:<N>` — max companies to find (default: 20)

**Pipeline**:

```
Phase 1: Strategy      — Define target profile, scoring criteria, outreach angles
Phase 2: Sources       — Research best directories for the region/sector
Phase 3: Scout + Dedup — Discover companies from multiple sources in parallel
Phase 4: Scan          — Check reputations on Glassdoor, Trustpilot, Indeed, Google Business
Phase 5: Enrich        — Contacts, news, growth signals, tech stack (parallel per company)
Phase 6: Score         — Weighted scoring across all intelligence dimensions
Phase 7: Write Cards   — Per-company markdown dossier cards
Phase 8: Report        — Executive summary with scored ranking
```

### Output Structure

Every run produces a self-contained directory:

```
.mz/outreach/<run_name>/
├── companies/
│   ├── <company>.json          # Machine-readable enriched data
│   ├── <company>.md            # Human-readable dossier card
│   └── ...
├── strategy.json               # Target profile and scoring weights
├── sources.json                # Directories and platforms used
├── scout_summary.md            # Discovery results
└── <date>_outreach_<goal>.md   # Executive summary report (date is YYYY_MM_DD)
```

Each company gets exactly two permanent files — a JSON (for programmatic use) and a markdown card (for reading). No bulk arrays.

### Resume Support

The pipeline saves state after each phase. If interrupted, re-running the same command resumes from where it left off.

### `/outreach-enrich-company` — Deep Enrichment + Letter Drafting

Takes an existing company card `.md` (produced by `/outreach-research`), fans out 5 specialist subagents to find **what the base research missed** — fresh news, deeper tech-stack signals, growth trajectory updates, reputation deltas, and additional decision-makers — then drafts one naturalized outreach letter per Key Contact (best channel each: email when available, LinkedIn DM as fallback). Everything is appended back into the source card as `## Deeper Intelligence` and `## Outreach Letters` sections. On completion the card is relocated to `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` with the last-interaction-date prefix.

Every letter opens with a salutation, carries a subject (email only — LinkedIn DMs have no subject field), and closes with a voice-adaptive gratitude sign-off (`Thanks,` / `Best regards,` / `Sincerely,`), written in plain ASCII with no em-dashes or other AI-artifact punctuation.

Each letter is also subtly calibrated to the contact's inferred communication style (Social Styles, grounded only in public professional signal via `outreach-personality-profiler`; it falls back to role-based priorities when the footprint is thin and never names the trait in the text). Disable with `personality:off`.

```
/outreach-enrich-company .mz/outreach/<run>/companies/acme.md
/outreach-enrich-company .mz/outreach/active/2026-05-12_acme.md channels:email
/outreach-enrich-company <card> enrich:only            # deepen without drafting letters
/outreach-enrich-company <card> enrich:skip            # draft letters without re-enriching
```

**Parameters**:

- `channels:email|linkedin|both` — which channels to draft (default: both, best-per-contact)
- `enrich:both|only|skip` — control enrichment vs. letter drafting (default: both)
- `sender:<inline voice or path>` — sender voice override (default: strategy.json or fallback)
- `personality:off` — disable reader-style calibration (default: on; footprint profiling runs automatically when a contact has a usable public profile)

**Pipeline**:

```
Phase 0: Setup          — Parse args, validate card, derive task name
Phase 1: Parse + Web    — Extract card data, light web pass, write card_parsed.json
Phase 2: Deep Enrich    — Dispatch 5 subagents in parallel for gap-fill intelligence
Phase 3: Brief + Draft  — Build briefs, profile each contact's reader style, draft via expert-copywriter
Phase 4: Naturalize     — Run expert-naturalizer in-place on every draft (mandatory)
Phase 5: Card Rewrite   — Assemble Deeper Intelligence + Outreach Letters sections,
                          relocate card to .mz/outreach/active/
Phase 6: Verify         — Report counts, surface concerns, STATUS line
```

### `/outreach-update-card` — Interaction Log Append

Append a dated interaction entry (call, email-sent, reply-received, meeting, status-change, etc.) to the bottom of a company card under `## Interaction History`. Idempotent and additive — never rewrites or deletes prior entries. On every update the card is relocated to `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` with the new last-interaction date as the prefix.

```
/outreach-update-card .mz/outreach/<run>/companies/acme.md action:"Sent intro email to Jane Doe"
/outreach-update-card .mz/outreach/active/2026-05-10_acme.md action:"Reply received - interested" date:2026-05-15
```

**Parameters**:

- `action:"<one-line description>"` — required, what you did or what happened
- `date:<YYYY-MM-DD>` — override the entry date (default: today)
- `outcome:<positive|neutral|negative>` — optional sentiment tag

## Agents

Specialized workers coordinated by the skills. You don't invoke these directly.

| Agent                                | Role                                                                                                                                                                 |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **outreach-strategist**              | Defines target company profile, search criteria, scoring weights, and outreach angles                                                                                |
| **outreach-source-researcher**       | Identifies best business directories and aggregator platforms for the region/sector                                                                                  |
| **outreach-scout**                   | Discovers companies from a specific directory or data source                                                                                                         |
| **outreach-scanner**                 | Scans companies against review/reputation platforms for scores and sentiment                                                                                         |
| **outreach-enrichment-orchestrator** | Coordinates per-company enrichment by dispatching the 4 enrichment agents                                                                                            |
| **outreach-contact-finder**          | Finds emails, phone numbers, key decision-makers, LinkedIn profiles                                                                                                  |
| **outreach-personality-profiler**    | Reads one contact's public footprint and returns a Social-Styles read plus a subtle letter-calibration directive, grounded-only (used by `/outreach-enrich-company`) |
| **outreach-news-finder**             | Finds recent news, funding rounds, partnerships, press releases                                                                                                      |
| **outreach-growth-analyst**          | Analyzes job postings, hiring patterns, team size, growth trajectory                                                                                                 |
| **outreach-tech-analyst**            | Analyzes technology stack, engineering maturity, open-source presence                                                                                                |
| **outreach-card-writer**             | Writes comprehensive markdown dossier card from enriched company JSON                                                                                                |
| **outreach-reporter**                | Synthesizes all intelligence into a scored executive summary                                                                                                         |
| **outreach-climate-source-finder**   | Ranks local business-climate sources for one industry × region (used by `/outreach-brief`)                                                                           |
| **outreach-climate-researcher**      | Extracts dated local-climate signals and proposal hooks for one industry × region                                                                                    |

The 5 enrichment-tier agents (`outreach-contact-finder`, `outreach-news-finder`, `outreach-growth-analyst`, `outreach-tech-analyst`, `outreach-scanner`) are reused by `/outreach-enrich-company` for gap-fill enrichment — they receive the prior research as context and are instructed to surface only **new** findings.

## Scoring (outreach-research)

Companies are scored across multiple dimensions with configurable weights (set by the strategist based on your outreach goal):

- **Reputation** — review scores, sentiment, public perception
- **Growth signals** — hiring velocity, team expansion, funding
- **Tech fit** — stack alignment, engineering maturity
- **Timing** — recent news, funding rounds, partnerships
- **Contact accessibility** — decision-maker reachability

The executive report ranks companies by composite score with individual dimension breakdowns.

## Card Lifecycle

```
1. /outreach-research          → .mz/outreach/<run>/companies/<slug>.md     (baseline card)
2. /outreach-enrich-company    → same path + ## Deeper Intelligence + ## Outreach Letters
                                  → relocated to .mz/outreach/active/<YYYY-MM-DD>_<slug>.md
3. /outreach-update-card       → appends ## Interaction History entry, refreshes prefix date
```

The prefix date on the active-folder filename reflects the most recent interaction, so a directory listing sorts cards by recency naturally.

## License

MIT
