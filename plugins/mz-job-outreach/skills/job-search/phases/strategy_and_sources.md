# Phases 1-2: Strategy and Source Assembly

## Phase 1: Strategy

Dispatch `job-strategist`:

```
Build the job-search strategy.

CV path: <CV_PATH>
Free-text preferences: "<PREFERENCES>"
Recency window (days): <RECENCY_DAYS>
Output file: <RUN_DIR>/search_strategy.json

Read the CV, parse the preferences, derive search queries per top job title,
specify the location-eligibility rule, and emit the strategy JSON. The JSON
must include the full schema:

- derived_from_cv (titles, skills, seniority, languages, location, work auth)
- preferences (parsed from $ARGUMENTS body)
- search_queries (3-5 per top title)
- title_aliases (4-6 per top title — recall expansion for scout)
- bilingual_query_variants (ONLY when CV has non-English at B2+; ISO-639-1 keyed)
- must_have_skills (2-4 from CV — primary stack)
- must_have_or_groups (when user wrote "X or Y" preferences)
- nice_to_have_skills (everything else from CV)
- synonym_clusters (3-6 terms per skill — must-haves + top 5 nice-to-haves)
- location_eligibility_rule
- scoring_weights + scoring_rationale
- recency_window_days
- notes

If the CV lacks a current location AND the user requires remote work, return
STATUS: NEEDS_CONTEXT and list `current_location` as the missing field — do
not guess.
```

Read `search_strategy.json`. Extract derived job titles, must-have/nice-to-have skill split, synonym clusters, title aliases, bilingual query variants, location-eligibility rule, query templates, scoring weights echo.

Validate the strategy file contains all required fields before proceeding:

- `must_have_skills` is a non-empty array (unless CV has fewer than 5 listed skills, in which case `DONE_WITH_CONCERNS` is acceptable).
- Every entry in `must_have_skills` appears in `derived_from_cv.skills`.
- `synonym_clusters` has an entry for each `must_have_skills` member.
- `title_aliases` keys match `derived_from_cv.top_titles`.
- If `bilingual_query_variants` is present, the language code is ISO-639-1 and there is at least one non-English entry at B2+ in `languages_spoken`.

If validation fails, re-dispatch the strategist once with the specific gap listed; on a second failure, set `state.md` `Status` to `aborted_strategy_invalid` and stop.

If the agent returns `STATUS: NEEDS_CONTEXT` with `current_location` missing:

1. Emit a chat block before AskUserQuestion:

   ```
   **Current location needed**
   The CV does not specify a current location, but your preferences require remote
   work. The skill needs to know where you are so it can filter listings that
   exclude your country/region.

   - Provide a city + country (e.g. "Berlin, Germany")
   - Or **Cancel** to abort
   ```

1. Invoke `AskUserQuestion`:

   ```
   What is your current location (city, country)? Used only to verify which
   remote listings allow workers from your country. Type your answer or
   **Cancel** to abort.
   ```

1. On Cancel → set `Status` to `aborted_by_user` in state.md, stop.

1. Otherwise re-dispatch `job-strategist` with the supplied location appended to the prompt; overwrite `search_strategy.json`.

Update `.mz/task/<task_name>/state.md` `Phase` field to `strategy_complete`.

Proceed to Phase 1.5 before launching Phase 2.

______________________________________________________________________

## Phase 1.5: User Approval of Strategy

Handled by the orchestrator per the inline section in `SKILL.md` (two-surface gate, verbatim JSON, loop until approve). After approval, update `state.md` `Phase` to `strategy_approved` and continue here.

______________________________________________________________________

## Phase 2: Source Assembly (canonical + researcher augmentation)

Sources are assembled in two steps: canonical defaults always queried, plus dynamic augmentation by the researcher agent for niche/regional boards.

### Step 2.1 — Canonical defaults

Canonical job-board defaults are stored in the skill's own data file at `${CLAUDE_PLUGIN_ROOT}/skills/job-search/sources/job_canonical.json`. The orchestrator copies this array into `<RUN_DIR>/sources.json` as the baseline.

```bash
cp "${CLAUDE_PLUGIN_ROOT}/skills/job-search/sources/job_canonical.json" "<RUN_DIR>/sources.json"
```

Each entry already carries `tier: "canonical"`, `scrape_allowed: true`, and `language_hint: "en"`. The file currently lists 10 boards: LinkedIn Jobs, Indeed, Wellfound, RemoteOK, WeWorkRemotely, Hacker News Who-Is-Hiring, Otta, Lever ATS (via Google), Greenhouse ATS, and Ashby ATS.

If the copy fails (file missing, unreadable), set `state.md` `Status` to `aborted_canonical_missing` and stop — the canonical list is required.

### Step 2.2 — Researcher augmentation

Before dispatching the researcher, compute the CV hash for yield-history lookup:

```bash
mkdir -p .mz/outreach/_history
# Normalize CV by lowercasing + collapsing whitespace, then SHA-1.
cv_hash=$(tr '[:upper:]' '[:lower:]' < "<CV_PATH>" | tr -s '[:space:]' ' ' | sha1sum | cut -c 1-40)
```

If `.mz/outreach/_history/source_quality.json` does not exist, the researcher reads an empty file (initialized lazily) — no need to pre-create it.

Dispatch `job-source-researcher`:

```
Augment the canonical job-board list with niche or regional sources.

Mode: job
Canonical file: ${CLAUDE_PLUGIN_ROOT}/skills/job-search/sources/job_canonical.json
Strategy file: <RUN_DIR>/search_strategy.json
Existing canonical sources file: <RUN_DIR>/sources.json
Source-yield history: .mz/outreach/_history/source_quality.json (treat as empty if missing)
CV hash: <cv_hash>
Output: append to <RUN_DIR>/sources.json (read first, merge, write back)

Add 2-6 boards that fit the CV's region, language, or specialty signals
(e.g. Arbeitnow for DE/EU tech, Remotive for global remote, YC Work at a
Startup for early-stage). Score each 1-10; include only >= 5.

Skip any source whose verdict from yield history is `demote` (every recorded
run for this cv_hash had top_n_hits == 0, with >= 3 recorded runs).

Tag each emitted entry with `language_hint` (ISO-639-1, default "en"; use
the matching code when the source's listings are predominantly non-English).
Annotate canonical entries with `language_hint: "en"` on read-back; do not
modify their other fields.

Do NOT duplicate any canonical entry. Total combined entries must not
exceed 10.
```

After the researcher completes, validate `sources.json`:

- Total entries: 5–10 (canonical + augmented).
- Every entry has `name`, `url`, `type`, `tier`, `relevance_score`, `scrape_hints`, `access_notes`, `language_hint`.
- Researcher-added entries have `tier: "augmented"` and `yield_history_verdict ∈ {"neutral", "boost"}` (never `"demote"`).

If the researcher returns fewer than 2 augmentations and the user CV signals a strong niche (specific country language, specialty stack), log a `DONE_WITH_CONCERNS` note in `state.md` Errors but continue — canonical defaults alone are still usable.

Update `.mz/task/<task_name>/state.md` `Phase` field to `sources_complete`.

Proceed to Phase 3. Read `phases/scout_score_enrich_report.md`.
