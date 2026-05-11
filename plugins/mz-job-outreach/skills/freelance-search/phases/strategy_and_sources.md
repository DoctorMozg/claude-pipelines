# Phases 1-2: Strategy and Source Assembly (freelance mode)

## Phase 1: Strategy

Dispatch `freelance-strategist`:

```
Build the freelance-search strategy.

CV path: <CV_PATH>
Free-text preferences: "<PREFERENCES>"
Region scope: <REGION_SCOPE>
Recency window (days): <RECENCY_DAYS>
Output file: <RUN_DIR>/search_strategy.json

Read the CV, parse preferences, detect the candidate's primary discipline
plus up to 2 secondary disciplines, derive search queries per top freelance
title, normalize the rate floor to all three formats ($/hr, $/day,
project-total) with FX→USD math surfaced verbatim in notes, encode region
eligibility per the runtime region_scope, and emit the strategy JSON with
the full freelance schema:

- derived_from_cv (titles, skills, seniority, languages, location,
  discipline, secondary_disciplines, prior_freelance_experience)
- preferences (engagement_types subset of [project_gig, contractor_placement,
  consulting_advisory] — NEVER fractional_retainer; regions_allowed;
  vetted_only; excluded_companies)
- rate_floor (hourly_usd, daily_usd, project_total_usd, fx_basis,
  normalization_notes)
- search_queries (3-5 per top title, freelance-flavored)
- title_aliases (4-6 per top title)
- bilingual_query_variants (ISO-639-1 keyed, ONLY when CV has B2+ in the
  matching language AND that region is in regions_allowed)
- must_have_skills, nice_to_have_skills
- location_eligibility_rule (derived from region_scope)
- scoring_weights (skill_match=40, location_eligibility=15, scope_clarity=10,
  budget_fit=10, client_vetting_presence=10, recency=10, discipline_fit=5)
- scoring_rationale, recency_window_days, notes

If the CV lacks a current location AND region_scope is "CV-driven", return
STATUS: NEEDS_CONTEXT and list `current_location` as the missing field.
```

Read `search_strategy.json`. Extract derived discipline, must-have/nice-to-have split, title aliases, bilingual variants, location-eligibility rule, query templates, scoring weights echo, and rate-floor three-format.

Validate the strategy file contains all required fields before proceeding:

- `derived_from_cv.discipline` is one of the allowed enum values.
- `preferences.engagement_types` is a non-empty subset of the three allowed values and does NOT contain `fractional_retainer`.
- `rate_floor.hourly_usd`, `daily_usd`, `project_total_usd` are all present (or all `null` if user gave no floor).
- `must_have_skills` is non-empty (unless CV has fewer than 5 skills — `DONE_WITH_CONCERNS` acceptable).
- Every `must_have_skill` appears in `derived_from_cv.skills`.
- `title_aliases` keys match `derived_from_cv.top_titles`.
- `scoring_weights` values sum to 100.

If validation fails, re-dispatch once with the specific gap; second failure → `Status: aborted_strategy_invalid` and stop.

If the agent returns `STATUS: NEEDS_CONTEXT` with `current_location` missing:

1. Emit a chat block:

   ```
   **Current location needed**
   The CV does not specify a current location, but your region scope is CV-driven. The skill needs to know where you are so it can filter gigs that exclude your country/region.

   - Provide a city + country (e.g. "Berlin, Germany")
   - Or **Cancel** to abort
   ```

1. Invoke `AskUserQuestion`:

   ```
   What is your current location (city, country)? Used only to verify which freelance gigs allow contractors from your country. Type your answer or **Cancel** to abort.
   ```

1. Cancel → `Status: aborted_by_user`, stop.

1. Otherwise re-dispatch with the location appended.

Update `state.md` `Phase` to `strategy_complete`.

Proceed to Phase 1.5 before launching Phase 2.

______________________________________________________________________

## Phase 1.5: User Approval of Strategy

Handled by the orchestrator per the inline section in `SKILL.md` (two-surface gate, verbatim JSON, loop until approve). After approval, update `state.md` `Phase` to `strategy_approved` and continue here.

______________________________________________________________________

## Phase 2: Source Assembly (canonical freelance + researcher augmentation)

Sources are assembled in two steps: canonical freelance defaults (split into `scrape_sources` and `guidance_sources` arrays) plus dynamic augmentation by the researcher with `mode: "freelance"`.

### Step 2.1 — Canonical freelance defaults

Canonical freelance sources are stored at `${CLAUDE_PLUGIN_ROOT}/skills/freelance-search/sources/freelance_canonical.json`. The file has two arrays: `scrape_sources` (12 entries — Arc.dev, Gun.io, Braintrust, Lemon.io, Toptal, Malt, YunoJuno, Worksome, freelance.de, Contra, Codementor, Dribbble Jobs) and `guidance_sources` (6 entries — MarketerHire, South Park Commons, On Deck, Lenny's, Reforge, Working Not Working).

Copy both arrays into `<RUN_DIR>/sources.json` as a single flat array:

```bash
jq '.scrape_sources + .guidance_sources' \
   "${CLAUDE_PLUGIN_ROOT}/skills/freelance-search/sources/freelance_canonical.json" \
   > "<RUN_DIR>/sources.json"
```

Every canonical entry already carries `tier: "canonical"`, `language_hint`, `scrape_allowed` (true for scrape entries, false for guidance entries), and `discipline`.

If the copy fails (file missing, jq unavailable), set `state.md` `Status` to `aborted_canonical_missing` and stop.

### Step 2.2 — Researcher augmentation (freelance mode)

Compute the CV hash for yield-history lookup if not already in state:

```bash
mkdir -p .mz/outreach/_history
cv_hash=$(tr '[:upper:]' '[:lower:]' < "<CV_PATH>" | tr -s '[:space:]' ' ' | sha1sum | cut -c 1-40)
```

Dispatch `job-source-researcher`:

```
Augment the canonical freelance-board list with niche or regional sources.

Mode: freelance
Canonical file: ${CLAUDE_PLUGIN_ROOT}/skills/freelance-search/sources/freelance_canonical.json
Strategy file: <RUN_DIR>/search_strategy.json
Existing canonical sources file: <RUN_DIR>/sources.json
Source-yield history: .mz/outreach/_history/source_quality.json (treat as empty if missing)
CV hash: <cv_hash>
Output: append to <RUN_DIR>/sources.json (read first, merge, write back)

Add 2-6 scrape boards that fit the candidate's discipline, region, language,
or engagement-type signals. Score each 1-10; include only >= 5.

If the candidate's discipline + seniority profile matches a high-signal
referral-only network not already in canonical (e.g. Catalant for senior
consulting), you may also emit up to 3 guidance entries with
`scrape_allowed: false` and a `guidance_note` describing the access path.

Banned sources: upwork.com, fiverr.com, peopleperhour.com, freelancer.com,
guru.com — user-locked exclusion.

Skip any source whose verdict from yield history is `demote`.

Tag each emitted entry with `language_hint` (ISO-639-1, default "en"; use
the matching code when listings are predominantly non-English) and
`scrape_allowed` (true or false). Annotate canonical entries with missing
`scrape_allowed` on read-back if needed; do not modify other canonical fields.

Total combined scrape entries (canonical + augmented) must not exceed 10.
Total guidance entries (canonical + augmented) must not exceed 9.
```

After the researcher completes, validate `sources.json`:

- Scrape entries (`scrape_allowed: true`): 5–10 (canonical + augmented).
- Guidance entries (`scrape_allowed: false`): 0–9.
- Every entry has `name`, `url`, `type`, `tier`, `language_hint`, `scrape_allowed`.
- Researcher-added entries have `tier: "augmented"` and `yield_history_verdict ∈ {"neutral", "boost"}` (never `"demote"`).
- No entry's URL matches the banned domain list (`upwork.com`, `fiverr.com`, `peopleperhour.com`, `freelancer.com`, `guru.com`).

If the researcher returns fewer than 2 augmentations and the user CV signals a strong niche, log a `DONE_WITH_CONCERNS` note in `state.md` Errors but continue — canonical defaults alone are usable.

Update `state.md` `Phase` to `sources_complete`.

Proceed to Phase 3. Read `phases/scout_score_report.md`.
