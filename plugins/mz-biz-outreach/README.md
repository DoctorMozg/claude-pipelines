# mz-biz-outreach

Autonomous business-outreach pipelines for Claude Code. Two complementary skills: `/outreach-research` finds **companies to sell to** — discovers, scans, enriches, scores, and reports. `/outreach-contacts` does **one-shot contact discovery** for a single named company — decision-makers, emails, phones, and social presence, without running the full pipeline.

> Looking for job-hunting tools (`/job-search`, `/job-recruiter-info`)? Those moved to a dedicated plugin: **`mz-job-outreach`**.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-biz-outreach
```

## Skills

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

### `/outreach-contacts` — Single-Company Contact Discovery

One-shot contact lookup for a single named company. Skip the full pipeline when you already know who you want to reach but just need the contacts. Builds a minimal target JSON, dispatches the same `outreach-contact-finder` agent used by `/outreach-research` enrichment, and writes a compact markdown report with named decision-makers, verified emails, phones, and social channels.

```
/outreach-contacts Acme Corp
/outreach-contacts acme.com decision_makers:CTO,VP-Engineering
/outreach-contacts Stripe region:US decision_makers:Head-of-Platform
```

**Parameters**:

- `decision_makers:<roles>` — comma-separated priority roles (default: inferred from company size)
- `region:<value>` — disambiguation hint when the company name is ambiguous

**Pipeline**:

```
Phase 0: Setup       — Parse args, resolve company name ↔ domain
Phase 1: Contact     — Dispatch outreach-contact-finder against the target
Phase 2: Report      — Compact markdown with decision-makers, emails, phones, social
```

**Output**:

```
.mz/outreach/<YYYY_MM_DD>_outreach_contacts_<slug>/
├── target.json                          # Parsed target + role priorities
├── contacts.json                        # Raw agent output
└── <YYYY_MM_DD>_outreach_contacts_<slug>.md  # Final markdown report
```

## Agents

Specialized workers coordinated by the skills. You don't invoke these directly.

| Agent                                | Role                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| **outreach-strategist**              | Defines target company profile, search criteria, scoring weights, and outreach angles |
| **outreach-source-researcher**       | Identifies best business directories and aggregator platforms for the region/sector   |
| **outreach-scout**                   | Discovers companies from a specific directory or data source                          |
| **outreach-scanner**                 | Scans companies against review/reputation platforms for scores and sentiment          |
| **outreach-enrichment-orchestrator** | Coordinates per-company enrichment by dispatching the 4 enrichment agents             |
| **outreach-contact-finder**          | Finds emails, phone numbers, key decision-makers, LinkedIn profiles                   |
| **outreach-news-finder**             | Finds recent news, funding rounds, partnerships, press releases                       |
| **outreach-growth-analyst**          | Analyzes job postings, hiring patterns, team size, growth trajectory                  |
| **outreach-tech-analyst**            | Analyzes technology stack, engineering maturity, open-source presence                 |
| **outreach-card-writer**             | Writes comprehensive markdown dossier card from enriched company JSON                 |
| **outreach-reporter**                | Synthesizes all intelligence into a scored executive summary                          |

`outreach-contact-finder` is shared between `/outreach-research` enrichment and the standalone `/outreach-contacts` skill — same contract, two entry points.

## Scoring (outreach-research)

Companies are scored across multiple dimensions with configurable weights (set by the strategist based on your outreach goal):

- **Reputation** — review scores, sentiment, public perception
- **Growth signals** — hiring velocity, team expansion, funding
- **Tech fit** — stack alignment, engineering maturity
- **Timing** — recent news, funding rounds, partnerships
- **Contact accessibility** — decision-maker reachability

The executive report ranks companies by composite score with individual dimension breakdowns.

## License

MIT
