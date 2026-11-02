# Phases 3-4.5: Scout, Filter, Pre-score

## Phase 3: Scout fan-out

### 3.1 Dispatch scouts

- **MAX_SCOUTS_PER_WAVE**: 6

Spawn one `job-scout` per source from `sources.json`, in parallel **waves of ≤MAX_SCOUTS_PER_WAVE (6) concurrent agents per single assistant message**. If `sources.json` contains more than 6 sources, dispatch in sequential waves until every source has been scouted. Scouts are writer agents (they write `<RUN_DIR>/_scout/<source_slug>.json`). Wait for every agent in the wave to report, then check that each artifact exists on disk before using it.

Per-source dispatch prompt:

```
Scout job listings from this source.

Source: <name>, URL: <url>, Type: <type>, Tier: <tier>
Scrape hints: <scrape_hints>
Access notes: <access_notes>

Strategy file: <RUN_DIR>/search_strategy.json
Recency window (days): <RECENCY_DAYS>
Per-source result cap: <ceil(limit * 2 / source_count), minimum 15, maximum 50>

Write results to: <RUN_DIR>/_scout/<source_slug>.json

Read search_strategy.json for the derived job titles, skill keywords,
employment-type filter, region, and location-eligibility rule. Build 3+
query variants per top job title (direct, site-specific, aggregator).
Extract per-listing: title, company, location_string, remote_status_raw,
url, posted_date, salary_string, summary_snippet.

If the source returns zero results for every query, run a smoke test
(e.g. `<title> jobs` with no filters). Emit ZERO RESULTS VERIFIED if
the smoke test also returns nothing; ZERO RESULTS UNVERIFIED if the
smoke test was blocked; never emit a silent empty.
```

### 3.2 Wait and validate

After all scouts return, validate each `_scout/<source_slug>.json` exists and is a valid JSON array. Empty results are recorded but do not abort the phase. If **every** scout returned zero and each reported `ZERO RESULTS VERIFIED`, there is nothing to rank: set `Status: complete` with `Phase: zero_listings` and `what_remains: []`, tell the user, and stop. If any scout reported `ZERO RESULTS UNVERIFIED` or no verdict, set `Status: blocked` with `what_remains: [awaiting answer: widen the search, or stop]` and stop.

Update `state.md` `Phase` to `scout_complete` and add `ListingsScraped: <total>` field.

______________________________________________________________________

## Phase 4: Normalize, dedupe, filter (inline)

The orchestrator handles Phase 4 inline with Bash + Read + jq (no agent needed).

Sub-step order is fixed: **4.1 URL dedup → 4.2 Fingerprint dedup → 4.3 Recency → 4.4 Industry/attribute blocklist → 4.5 Salary normalization → 4.6 Location-eligibility → 4.7 Persist**.

### 4.1 Concat and URL dedup

```bash
cd "<RUN_DIR>"
# Merge all scout outputs into one array.
jq -s 'add' _scout/*.json > raw_listings_all.json
```

Read `raw_listings_all.json`. Dedup by canonical URL:

1. Strip query parameters listed below (case-insensitive): `utm_*`, `gclid`, `fbclid`, `mc_cid`, `mc_eid`, `ref`, `source`, `trk`.
1. Lowercase host. Strip trailing slash. Strip URL fragments.
1. For collisions, keep the entry with the most non-null fields; merge `source` into a list.

### 4.2 Cross-source fingerprint dedup

After URL dedup, the same posting still shows up under different URLs when scraped from LinkedIn + the company's careers page + an ATS host. Collapse these by fingerprint:

1. For each listing, compute:
   - `title_normalized` = lowercase, strip punctuation, collapse whitespace, strip seniority prefix synonyms (`sr.|senior|staff|principal|lead`), strip suffix words (`engineer|developer|programmer`).
   - `company_normalized` = lowercase, strip legal suffixes (`inc`, `ltd`, `gmbh`, `llc`, `s.a.`, `s.r.l.`), strip punctuation.
   - `location_country` = country code or `"remote"` (parsed from `location_string` or `remote_status_raw`; fall back to `"unknown"`).
1. Group by the tuple `(title_normalized, company_normalized, location_country)`.
1. For each group of ≥ 2 entries:
   - Keep the entry with the **earliest** parseable `posted_date` (oldest posting wins — that's the original).
   - Merge `source` from collapsed entries into the survivor's `source` list (deduped).
   - Merge `salary_string` only if survivor's is null/empty.
   - Set `merged_from_urls: [<urls of dropped duplicates>]` on the survivor for audit.
1. Drop the collapsed entries.

Write the deduped array back to `raw_listings_all.json` before continuing.

### 4.3 Recency filter

For each listing:

- Parse `posted_date`. Accept ISO date, `YYYY-MM-DD`, `N days ago`, `today`, `yesterday`, and common board phrasing.
- If older than `RECENCY_DAYS` → drop the listing entirely.
- If missing or unparseable → keep, tag `recency_status: "unknown"`. The recency axis in scoring penalizes unknowns (50/100).
- Otherwise tag `recency_status: "fresh"` and compute `posted_days_ago`.

### 4.4 Industry / company-attribute blocklist (HARD GATE)

Read `search_strategy.json` `preferences.excluded_industries` (array of strings) and `preferences.excluded_company_attributes` (array of strings). Either may be empty.

For each listing, scan `title + company + summary_snippet + remote_status_raw` (case-insensitive, word-boundary):

- If any entry in `excluded_industries` matches → route the listing to `scored_jobs_excluded.json` with `excluded_reason: "industry_blocklist"`, `excluded_value: "<the matching term>"`. Do not advance.
- If any entry in `excluded_company_attributes` matches → route to `scored_jobs_excluded.json` with `excluded_reason: "attribute_blocklist"`, `excluded_value: "<the matching term>"`. Do not advance.

A single listing can hit both — record the first that triggers and stop scanning.

Surviving listings continue to Phase 4.5.

### 4.5 Salary normalization with FX

For each surviving listing, parse `salary_string` into a structured `salary_normalized` object:

```json
{
  "currency": "EUR|USD|GBP|...",
  "min": 80000,
  "max": 110000,
  "period": "year|month|hour|day",
  "normalized_annual_min_usd": 86400,
  "normalized_annual_max_usd": 118800,
  "raw": "<original salary_string verbatim>"
}
```

Parser rules:

1. Detect currency from prefix/suffix symbols (`$`, `€`, `£`, `₹`, `¥`, `CHF`, `SEK`, `NOK`, `DKK`, `PLN`, `AUD`, `CAD`) or explicit codes.

1. Detect range: `<min>` – `<max>` (en-dash, em-dash, hyphen, "to", "до", "bis"). If single value, set both min and max to that value.

1. Detect `k`/`K` shorthand → multiply by 1000. Detect explicit `,000` thousands separators (drop them).

1. Detect period: `/yr`, `per year`, `annual`, `p.a.` → `year` (default if absent). `/mo`, `per month` → `month`. `/hr`, `per hour` → `hour`. `/day` → `day`.

1. Compute annual: `month × 12`, `hour × 2080` (40h × 52w), `day × 240` (working days/year).

1. Convert to USD via a fixed FX table baked into the orchestrator below (these are reference rates, not live — accuracy is acceptable to ±5%):

   | Currency | USD per unit |
   | -------- | ------------ |
   | USD      | 1.00         |
   | EUR      | 1.08         |
   | GBP      | 1.27         |
   | CHF      | 1.13         |
   | CAD      | 0.74         |
   | AUD      | 0.66         |
   | SEK      | 0.095        |
   | NOK      | 0.092        |
   | DKK      | 0.145        |
   | PLN      | 0.25         |
   | INR      | 0.012        |
   | JPY      | 0.0066       |

   For currencies not in the table, set `normalized_annual_min_usd` and `normalized_annual_max_usd` to `null` and tag `salary_normalized.fx_unknown: true`.

1. If `salary_string` is empty or unparseable, set `salary_normalized: null` and continue. The scorer treats null as neutral (70/100).

This object replaces vibes-based salary comparison with numeric comparison against `preferences.salary_floor_usd` (also normalized to USD/year by the strategist).

### 4.6 Location-eligibility extraction (HARD GATE)

Read `search_strategy.json` to get the user's `current_location` and the `remote_required` flag.

For each listing, scan `remote_status_raw + summary_snippet + location_string` with the following phrase/regex patterns (case-insensitive):

| Pattern                                        | Tag                                     |
| ---------------------------------------------- | --------------------------------------- |
| \`\\bremote\\b.{0,30}\\b(anywhere              | world                                   |
| \`\\bremote\\b.{0,30}\\b(US                    | United\\s\*States                       |
| \`\\bremote\\b.{0,30}\\b(UK                    | United\\s\*Kingdom)\\b\`                |
| \`\\bremote\\b.{0,30}\\b(EMEA                  | EU                                      |
| \`\\bremote\\b.{0,30}\\b(LATAM                 | Latin\\s\*America                       |
| `\beligible\s+to\s+work\s+in\s+([^.,;]{2,40})` | `work_auth_required: <captured region>` |
| \`\\bmust\\s+be\\s+(located                    | based                                   |
| \`\\b(no\\s+visa\\s+sponsorship                | cannot\\s+sponsor\\s+visa               |

Decision logic:

- `remote_required = false` (user accepts on-site/hybrid): `location_eligible = true` only if the listing's `location_string` is in `current_location`'s country or the listing is remote. Otherwise `false`.
- `remote_required = true`:
  - `remote_scope = anywhere` → `location_eligible = true`.
  - `remote_scope` is a specific region → `true` if `current_location` country is in that region, else `false`.
  - `location_required` captures a country/region → `true` if `current_location` matches, else `false`.
  - No pattern hits → `location_eligible = unknown`.
- `work_auth_strict = true` AND `current_location` country not in `work_auth_required` → force `location_eligible = false`.

Tag each surviving listing:

```json
{
  ...listing fields...,
  "recency_status": "fresh|unknown",
  "posted_days_ago": <int or null>,
  "location_eligibility": "true|false|unknown",
  "location_constraint_extracted": "<the phrase that drove the decision, verbatim>"
}
```

### 4.7 Persist

Write `raw_listings.json` containing every surviving listing tagged with `recency_status`, `posted_days_ago`, `salary_normalized`, `location_eligibility`, `location_constraint_extracted`, and (when applicable) `merged_from_urls`.

Blocklist-excluded listings (from 4.4) are appended to `scored_jobs_excluded.json` immediately with `final_score: null`, the listing's identifying fields, `excluded_reason`, and `excluded_value`. Do not delay this — the master report depends on `scored_jobs_excluded.json` being populated by the time Phase 8 runs.

Delete `_scout/` and `raw_listings_all.json` temp files.

Update `state.md` `Phase` to `filter_complete` and add `ListingsAfterFilter: <count>`, `ExcludedByBlocklist: <count>`.

______________________________________________________________________

## Phase 4.5: Cheap pre-score (LLM 0/1/2)

Dispatch `job-prescorer` agents in parallel waves of ≤6 to rate every surviving listing against the CV's must-have skills, or-groups, and synonym clusters. Listings rated `0` are dropped before the expensive full-score pass; `1` and `2` ratings advance.

### 4.5.1 Split into prescore batches

Read `raw_listings.json`. Eligible listings for pre-scoring are those with `location_eligibility != "false"` (i.e. `true` or `unknown`) AND not already excluded by the blocklist.

Compute `batch_count = ceil(len(eligible) / 15)`. The prescorer handles bigger batches than the full scorer because its per-listing output is one integer plus a short phrase.

Write each batch to `_prescore_batches/batch_<i>.json` (one array of listing objects per file).

### 4.5.2 Dispatch prescorers

Spawn `job-prescorer` agents in parallel waves of ≤6 concurrent agents per assistant message. Prescorers are writer agents (they write `_prescore_batches/batch_<i>_rated.json`). Wait for every agent in the wave to report, then check that each artifact exists on disk before using it.

Per-batch dispatch prompt:

```
Pre-score this batch of job listings against the CV's must-have skills.

CV path: <CV_PATH>
Strategy file: <RUN_DIR>/search_strategy.json
Batch file (input): <RUN_DIR>/_prescore_batches/batch_<i>.json
Output file: <RUN_DIR>/_prescore_batches/batch_<i>_rated.json

Read must_have_skills, must_have_or_groups, synonym_clusters, and
nice_to_have_skills from the strategy. Rate each listing 0/1/2:

  0 = no must-have or or-group matches; clearly off-stack.
  1 = partial match; full scorer should adjudicate.
  2 = every must-have and or-group satisfied (cluster terms count).

Emit one record per input listing with url, rating, matched_must_haves,
matched_or_groups, and a one-phrase reason (≤ 12 words). Recall-biased —
when uncertain, rate 1 not 0.
```

### 4.5.3 Merge and filter

After all prescorers return:

1. Concat `_prescore_batches/batch_*_rated.json` into one array.
1. Validate that the total number of ratings equals `len(eligible)`. If not, append a `DONE_WITH_CONCERNS` line to `state.md` Errors and proceed with what is present.
1. Build a `url → rating` map.
1. Partition `raw_listings.json` by rating:
   - `rating == 0` → append to `scored_jobs_excluded.json` with `excluded_reason: "prescore_zero"`, `prescore_reason: "<one-phrase reason from the prescorer>"`, `final_score: null`.
   - `rating ∈ {1, 2}` → keep for full scoring; attach `prescore_rating` to the listing record.
1. Write the surviving listings to `prescored_listings.json`.
1. Delete `_prescore_batches/` temp dir.

Update `state.md` `Phase` to `prescore_complete` and add `PrescoreDropped: <count>`, `PrescoreAdvanced: <count>`.

If `PrescoreAdvanced == 0`, stop the pipeline and set `Status: complete` with `Phase: zero_after_prescore` and `what_remains: []`, since there is nothing left to score. The user gets every excluded listing in the report footer regardless.

Proceed to Phase 5. Read `<SKILL_DIR>/phases/score_enrich_report.md`.
