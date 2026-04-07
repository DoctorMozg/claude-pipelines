# mz-biz-outreach

Autonomous business lead generation pipeline for Claude Code. Discovers companies, scans reputations, enriches with deep intelligence, scores leads, and produces executive reports with per-company dossier cards.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-biz-outreach
```

## Skills

### `/lead-gen` — Lead Generation Pipeline

Full autonomous outreach intelligence. Takes a target description and runs an 8-phase pipeline: defines strategy, researches sources, discovers companies, scans reputations, enriches with contacts/news/growth/tech data, scores leads, writes per-company dossier cards, and produces an executive summary.

```
/lead-gen find potential clients for our DevOps consulting in DACH region
/lead-gen SaaS companies in Latin America sector:HR-tech limit:30
/lead-gen find AI startups in Singapore for partnership opportunities
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
└── outreach_<date>_<goal>.md   # Executive summary report
```

Each company gets exactly two permanent files — a JSON (for programmatic use) and a markdown card (for reading). No bulk arrays.

### Resume Support

The pipeline saves state after each phase. If interrupted, re-running the same command resumes from where it left off.

## Agents

Specialized workers coordinated by the `/lead-gen` skill. You don't invoke these directly.

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

## Scoring

Companies are scored across multiple dimensions with configurable weights (set by the strategist based on your outreach goal):

- **Reputation** — review scores, sentiment, public perception
- **Growth signals** — hiring velocity, team expansion, funding
- **Tech fit** — stack alignment, engineering maturity
- **Timing** — recent news, funding rounds, partnerships
- **Contact accessibility** — decision-maker reachability

The executive report ranks companies by composite score with individual dimension breakdowns.

## License

MIT
