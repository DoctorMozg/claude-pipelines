# mz-job-outreach

Autonomous job-hunt and freelance-hunt pipelines for Claude Code. Four skills cover the two-axis matrix (salaried vs freelance × discovery vs targeted output):

- `/job-search` — **full CV-to-vacancies pipeline** for salaried roles (boards, ranking, recruiter contacts, cover letters).
- `/job-recruiter-info` — **one-shot recruiter discovery** for a single salaried role or company.
- `/freelance-search` — **full CV-to-gigs pipeline** for freelance/contract/consulting work (vetted networks, regional boards, niche boards; explicit Upwork/Fiverr exclusion).
- `/freelance-pitch` — **per-gig grounded proposal** for a selected freelance gig (≤350 words, milestones cited verbatim from gig scope, pricing cited verbatim from gig budget or strategist rate floor).

> Looking for B2B outreach tools (`/outreach-research`, `/outreach-contacts`)? Those live in the sibling plugin: **`mz-biz-outreach`**.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-job-outreach
```

## Skills

### `/job-search` — CV-to-Vacancies Pipeline

Takes a CV (markdown / plain text) plus a free-text preferences prompt, runs a 9-phase pipeline, and produces a single ranked master report plus per-job cover letters ready to copy-paste.

```
/job-search "Senior backend, Go or Rust, remote from Berlin only, no crypto, no on-call"
/job-search "Frontend React/TS, hybrid in Madrid, B2 Spanish ok" recency:14d limit:30
/job-search "Staff engineer, EU remote, no surveillance products" contacts:20 letters:20
```

**Parameters**:

- `limit:<N>` — max ranked listings to keep (default: 50)
- `recency:<N>d` — freshness window in days (default: 7)
- `contacts:<N>` — top-N to enrich with recruiter contacts (default: 10)
- `letters:<N>` — top-N to write cover letters for (default: 10)

Invocation collects the CV path interactively in Phase 0 via `AskUserQuestion`. There is exactly **one approval gate** — at Phase 1.5 — where you review and approve the derived search strategy before scraping begins.

**Pipeline**:

```
Phase 0:    Setup            — Parse args, ask for CV path, write state.md
Phase 1:    Strategy         — Derive titles, must-have/nice-to-have skills, synonym clusters,
                               title aliases, bilingual queries, region, scoring weights
Phase 1.5:  Approval gate    — User approves the strategy before any scraping
Phase 2:    Sources          — Canonical boards + researcher augmentation (regional/niche)
Phase 3:    Scout            — Parallel per-board listing extraction with adaptive query
                               expansion via title aliases (waves of ≤6)
Phase 4:    Normalize+filter — Cross-source fingerprint dedup, recency-filter,
                               location-eligibility (HARD GATE), industry/attribute blocklist,
                               salary normalization with FX
Phase 4.5:  Cheap pre-score  — Lightweight LLM rating 0/1/2 per listing; drop 0s, advance 1s+2s
Phase 5:    Score & rank     — Weighted multi-axis 0-100 with must-have hard gate (skill,
                               seniority, location, salary, recency, employer)
Phase 6:    Contacts top-N   — Recruiter/hiring-manager lookup for top jobs (waves of ≤6)
Phase 7:    Letters top-N    — Cover letters under 200 words, grounded in CV (waves of ≤6)
Phase 8:    Master report    — Single ranked markdown with contacts + letter links + excluded footer
```

**Search-quality features**:

- **Must-have skill hard gate** — strategist splits CV skills into must-haves vs nice-to-haves; listings missing every must-have (or every member of an OR group like `"Go or Rust"`) are routed to the excluded footer with `excluded_reason: "missing_must_have"`. The scorer never wastes tokens on them.
- **Synonym clusters** — every primary skill carries a cluster of equivalent/adjacent terms (`Rust → Tokio, async-std, Axum`; `Kubernetes → K8s, kube, EKS`). The pre-scorer and scorer credit any cluster term as evidence of the parent skill.
- **Title alias recall** — when a scout's primary queries return < 5 hits per source, it falls back to 4-6 alias forms per title (e.g. `Senior Backend Engineer → Sr. Backend Engineer, Server-Side Engineer, Senior Backend Developer`).
- **Bilingual queries** — CVs listing a non-English language at B2+ trigger native-language query variants for regional boards (e.g. DE candidates get `Software-Entwickler Backend remote Deutschland`).
- **Cross-source fingerprint dedup** — the same job posted to LinkedIn + Lever + the company's careers page is merged into one entry by `(title, company, location_country)` hash; earliest posted_date wins.
- **Industry / company-attribute blocklist** — `excluded_industries: ["crypto"]` and `excluded_company_attributes: ["no on-call"]` are enforced at Phase 4 as a hard filter, not just as a scorer concern.
- **Salary normalization with FX** — `salary_string` is parsed into `{currency, min, max, period, normalized_annual_usd}` so a `€80k-€110k` band can be compared to a `$100k` floor numerically instead of by vibes.
- **Two-stage scoring** — a cheap LLM pre-score rates each listing 0/1/2 against the CV's must-haves and synonym clusters; zeros are dropped, ones go through reduced scoring, twos advance to full multi-axis scoring. ~50-60% token reduction vs scoring every listing.
- **Source-yield memory** — sources that consistently produced zero top-N hits in the last 3 runs for this CV profile are demoted by the researcher on the next run. History lives in `.mz/outreach/_history/source_quality.json`.

**Output Structure**:

```
.mz/outreach/<YYYY_MM_DD>_job_search_<slug>/
├── search_strategy.json              # Phase 1 artifact (the approval-gate document)
├── sources.json                      # Canonical + augmented board list
├── raw_listings.json                 # Deduped, filtered, location-tagged
├── scored_jobs.json                  # Ranked top-N with contacts merged
├── scored_jobs_excluded.json         # Listings dropped by location mismatch (audit trail)
├── letters/
│   ├── <job_slug>.md                 # One cover letter per top-N job
│   └── ...
└── <YYYY_MM_DD>_job_search_<slug>.md # Master report — title + run summary + top-N detail + jobs 11-N table + sources + excluded footer + methodology
```

**Scoring axes** (weights):

- `skill_match` (40) — CV/listing skill overlap
- `seniority_fit` (15) — level alignment
- `location_eligibility` (15) — **HARD GATE**: listings that exclude your country are routed to the "Excluded — location mismatch" footer
- `salary_fit` (10) — versus an explicit salary floor (neutral 70 if unspecified)
- `recency` (10) — fresher postings score higher
- `employer_signals` (10) — listing quality and reputation markers

### `/job-recruiter-info` — Single-Job Recruiter Discovery

One-shot lookup for a single job listing or company — finds named recruiters, careers-page emails, LinkedIn handles, generic-pattern fallbacks, and the apply route. Skip the full pipeline when you already have a target role and just need the contacts.

```
/job-recruiter-info https://jobs.lever.co/acme/senior-backend
/job-recruiter-info "Acme Corp — Senior Backend Engineer"
/job-recruiter-info "Stripe" region:US language:en
```

**Parameters**:

- `region:<value>` — geographic hint (e.g. `region:DACH`, `region:EU`)
- `language:<value>` — recruiter-language hint (e.g. `language:de`, `language:fr`)

**Pipeline**:

```
Phase 0: Setup     — Parse target (URL or company+role), resolve domain
Phase 1: Contact   — Dispatch job-contact-finder via fallback chain
Phase 2: Report    — Compact markdown with named recruiter, careers email, apply URL, confidence
```

**Output**:

```
.mz/outreach/<YYYY_MM_DD>_job_recruiter_info_<slug>/
├── target.json                              # Parsed target
├── contacts.json                            # Raw agent output
└── <YYYY_MM_DD>_recruiter_info_<slug>.md    # Compact recruiter report
```

**Confidence levels**:

- `high` — named recruiter with verified email OR LinkedIn handle, AND a careers-page email
- `medium` — careers-page email only OR named recruiter on LinkedIn without email
- `low` — generic pattern guesses only OR contact form only

### `/freelance-search` — CV-to-Gigs Pipeline

Takes a CV plus free-text preferences and a region selection, runs a 7-phase pipeline against **vetted freelance networks** (Toptal, Arc.dev, Gun.io, Braintrust, Lemon.io), **regional boards** (Malt for EU, YunoJuno for UK, Worksome for Nordics, freelance.de for DACH), and **niche boards** (Contra, Codementor, Dribbble Jobs), and produces a single ranked master report with **top-N scored gigs** plus **DOC-ONLY guidance cards** for referral-only networks (MarketerHire, South Park Commons, On Deck, Lenny's, Reforge, Working Not Working).

**Explicitly excluded**: Upwork, Fiverr, PeoplePerHour, Freelancer.com, Guru — user-locked exclusion enforced by the source-researcher's freelance-mode blocklist.

```
/freelance-search "Senior backend freelance, Go/Rust, day rate €700+, prefer DACH"
/freelance-search "UX consulting, $200/hr floor, advisory only" recency:45d limit:30
/freelance-search "Frontend contract React/TS, 6+ months, remote EMEA, $80/hr+" pitches:top10
```

**Parameters**:

- `limit:<N>` — max ranked gigs to keep (default: 40)
- `recency:<N>d` — freshness window in days (default: 30 — freelance moves slower than salaried)
- `pitches:top<N>` — informational marker for how many top gigs you intend to pitch (default: 5)

Invocation collects the **CV path** and the **region scope** (`Global`, `EU`, `US`, `DACH`, `UK`, `France`, `CV-driven`) interactively in Phase 0. There is exactly **one approval gate** — at Phase 1.5 — where you review and approve the derived freelance strategy.

**Pipeline**:

```
Phase 0:    Setup + region pick    — Parse args, ask for CV path, ask for region scope, write state.md
Phase 1:    Strategy                — Detect discipline (eng/design/marketing/product/data/ops/founder),
                                      derive engagement-type filter (project_gig / contractor_placement /
                                      consulting_advisory), normalize rate floor to all three formats
                                      ($/hr, $/day, project-total) with FX→USD math
Phase 1.5:  Approval gate           — User approves the strategy before any scouting
Phase 2:    Sources                 — Canonical freelance boards (scrape + guidance) + researcher
                                      augmentation in freelance mode (enforces banned-domain blocklist)
Phase 3:    Scout                   — Parallel per-board gig extraction with adaptive query expansion
                                      via title aliases. Lexical engagement-type tagger emits
                                      candidate_engagement_types from scope/title text. Skips
                                      scrape_allowed:false guidance sources.
Phase 4:    Normalize+filter        — Cross-source URL dedup, engagement-type filter, recency filter,
                                      region filter, banned-domain refusal
Phase 4.5:  Cheap pre-score         — job-prescorer reused (format-agnostic) — drops 0s, advances 1s+2s
Phase 5:    Score & rank            — Weighted seven-axis 0-100 with must-have hard gate
                                      (skill_match=40, location_eligibility=15, scope_clarity=10,
                                      budget_fit=10, client_vetting_presence=10, recency=10,
                                      discipline_fit=5). Budget compared in listing's native rate
                                      format; conversion math surfaced verbatim in score_reason.
Phase 6:    Master report           — Single ranked markdown + DOC-ONLY guidance cards for
                                      scrape_allowed:false networks + excluded footer + yield-history
                                      update for next-run demotion
```

**Freelance-specific features**:

- **Three-format rate floor** — strategist normalizes the user's stated floor (any of hourly/daily/monthly/project/annual) into `hourly_usd`, `daily_usd`, `project_total_usd` simultaneously, with FX basis and conversion notes recorded verbatim. Scorer compares in the gig's native format and surfaces conversion math verbatim in `score_reason` so the user sees the math.
- **Engagement-type lexical tagger** — at scout time, gigs are tagged as `project_gig`, `contractor_placement`, and/or `consulting_advisory` based on explicit phrase matches (`"fixed-scope"`, `"40hr/week ongoing"`, `"advisory"`, `"audit"`, etc.) — not LLM judgment. Empty array is allowed; ambiguous gigs pass through to the scorer.
- **Vetted-network preference** — `client_vetting_presence` axis (10 points) credits canonical vetted networks (Toptal, Arc.dev, Gun.io, Braintrust, Lemon.io, YunoJuno, Worksome, Malt) higher than more open boards.
- **DOC-ONLY guidance** — referral/invite-only networks are surfaced as **cards** in the final report (with access path: "Apply at southparkcommons.com/apply", "Complete a Reforge course", "Get referred by an On Deck member") instead of being scraped. The pipeline never pretends to have listings it cannot reach.
- **Hardcoded mass-market blocklist** — `upwork.com`, `fiverr.com`, `peopleperhour.com`, `freelancer.com`, `guru.com` are blocked at the researcher and refused at the filter stage. User-locked exclusion.
- **Shared yield history** — same `.mz/outreach/_history/source_quality.json` as `/job-search`, keyed by `cv_hash` so source demotion follows the candidate across modes.

**Output Structure**:

```
.mz/outreach/<YYYY_MM_DD>_freelance_search_<slug>/
├── search_strategy.json                       # Phase 1 artifact (the approval-gate document)
├── sources.json                                # Canonical (scrape + guidance) + augmented boards
├── raw_gigs.json                               # Deduped, filtered, engagement-type tagged
├── scored.json                                 # Ranked top-N with verbatim score_reason
├── scored_excluded.json                        # Gigs dropped, with exclusion reasons
└── <YYYY_MM_DD>_freelance_search_<slug>.md    # Master report — summary + top-N + guidance cards + excluded footer
```

**Scoring axes** (weights):

- `skill_match` (40) — CV/gig skill overlap with must-have hard gate
- `location_eligibility` (15) — region eligibility against the runtime region scope
- `scope_clarity` (10) — deliverables + timeline presence in `project_scope_raw`
- `budget_fit` (10) — gig budget vs strategist rate floor in the gig's native format
- `client_vetting_presence` (10) — vetted/canonical/augmented tier of the source
- `recency` (10) — fresher gigs score higher (vs the 30-day default window)
- `discipline_fit` (5) — gig discipline vs CV's detected primary/secondary disciplines

### `/freelance-pitch` — Single-Gig Grounded Proposal

Generates one freelance proposal (≤350 words, hard cap) for a selected gig — referenced by rank from the latest `/freelance-search` run, by URL, or picked interactively.

```
/freelance-pitch 3                      # Top-3 gig from the latest run
/freelance-pitch https://malt.com/...   # Specific URL (looked up in latest run, or WebFetched off-pipeline with a warning)
/freelance-pitch                        # Interactive picker over latest run's top-10
```

**Hard grounding rules**:

- Every milestone must cite a verbatim noun phrase from `gig.project_scope_raw`. Ungrounded milestones are dropped with a `MILESTONE_UNGROUNDED:` warning.
- Every pricing bracket must cite either `gig.budget_range_raw` verbatim OR `strategy.rate_floor` verbatim. If both absent, the proposal uses `"Rate to be discussed"`.
- Banned phrases ("value-add", "end-to-end solution", "best practices", "tailored approach", "hit the ground running", "synergy", "leverage" as verb, etc.) are scanned and rewritten before emission.
- 350-word cap is strict.

**Pipeline**:

```
Phase 0:    Resolve gig             — Parse rank/URL/empty, look up in latest run or WebFetch off-pipeline
Phase 1:    Tone pick               — AskUserQuestion: Concise / Conversational / Formal
Phase 2:    Generate                — freelance-proposal-writer drafts with hard grounding rules
Phase 3:    Review + edit loop      — User approves, regenerates (up to 2), gives feedback, or cancels
Phase 4:    Write                   — Save to <run_dir>/proposals/<gig_slug>.md
```

**Output**:

```
.mz/outreach/<freelance-search-run-dir>/proposals/<gig_slug>.md    # When resolved against an existing run
.mz/outreach/<YYYY_MM_DD>_freelance_pitch_<slug>/proposals/<gig_slug>.md    # Off-pipeline mode (URL with no prior run)
```

The proposal markdown carries frontmatter (`gig_url`, `gig_title`, `client`, `source`, `generated_at`, `word_count`, `engagement_type_assumed`, `tone`) above the 5-section body (opener / approach / 2–3 milestones / pricing / closing).

## Agents

Specialized workers coordinated by the skills. You don't invoke these directly.

| Agent                         | Role                                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| **job-strategist**            | Parses the CV, derives titles/skills/region/queries/location-eligibility rule (salaried mode)          |
| **job-source-researcher**     | Augments canonical boards with niche/regional sources — mode-aware (`job` or `freelance`)              |
| **job-scout**                 | Extracts salaried vacancies from one assigned board with structured per-listing metadata               |
| **job-prescorer**             | Cheap 0/1/2 pre-rating against must-have skills + clusters — format-agnostic, used by both pipelines   |
| **job-scorer**                | Scores a salaried listing against the CV using the weighted multi-axis 0-100 model                     |
| **job-contact-finder**        | Finds named recruiters, careers emails, and LinkedIn handles for top-N salaried jobs                   |
| **job-letter-writer**         | Writes a sub-200-word cover letter per top-N salaried job, grounded in CV with no AI clichés           |
| **job-reporter**              | Synthesizes scored salaried jobs + excluded listings + letters into the master markdown report         |
| **freelance-strategist**      | Detects discipline + engagement-type filter + three-format rate floor; emits the freelance strategy    |
| **freelance-scout**           | Extracts freelance gigs from one board with scope + budget + engagement-type lexical tags              |
| **freelance-scorer**          | Scores a freelance gig 0-100 across 7 axes; compares budget in native rate format with conversion math |
| **freelance-proposal-writer** | Drafts a ≤350-word proposal grounded verbatim in gig scope and budget; bans AI clichés                 |

`job-contact-finder` is shared between `/job-search` Phase 6 and `/job-recruiter-info`. `job-source-researcher` is shared between `/job-search` and `/freelance-search` via the `mode` dispatch arg. `job-prescorer` is shared between `/job-search` and `/freelance-search` (format-agnostic skill matching).

## License

MIT
