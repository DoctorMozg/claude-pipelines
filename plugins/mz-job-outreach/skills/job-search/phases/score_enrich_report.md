# Phases 5-8: Score, Contacts, Letters, Report

## Phase 5: Full score & rank

Each `job-scorer` agent processes a batch of up to 10 listings. For `limit=50` that's 5 scorers in a single wave (under the 6-agent cap). For larger limits, use additional waves.

### 5.1 Split into batches

Compute `batch_count = ceil(len(eligible_listings) / 10)`. Eligible listings are those with `location_eligibility != "false"` (i.e. `true` or `unknown`).

Write each batch to a temp file `_score_batches/batch_<i>.json`.

### 5.2 Dispatch scorers

Per batch dispatch prompt:

```
Score this batch of job listings against the CV.

CV path: <CV_PATH>
Strategy file: <RUN_DIR>/search_strategy.json
Batch file (input): <RUN_DIR>/_score_batches/batch_<i>.json
Output file (in-place rewrite): <RUN_DIR>/_score_batches/batch_<i>_scored.json

For each listing, emit the score_breakdown, final_score, score_reason,
why_selected, and concerns. Use the full 0-100 range. Listings with
location_eligibility=false must be assigned final_score=null and
location_eligibility axis=0 — they will be routed to the excluded list.
```

### 5.3 Merge

After all scorers return:

1. Concat `_score_batches/batch_*_scored.json` into one array.
1. Partition: listings with `final_score=null` (location_eligibility=0 OR `location_eligibility=="false"` from Phase 4) go to `scored_jobs_excluded.json`. The rest go through ranking.
1. Sort by `final_score` descending. Truncate to `limit` (default 50).
1. Persist as `scored_jobs.json`.
1. Delete `_score_batches/` temp dir.

Update `state.md` `Phase` to `score_complete` and add `RankedJobs: <count>`, `ExcludedByLocation: <count>`.

______________________________________________________________________

## Phase 6: Contact-finder (top-N)

Read `scored_jobs.json`. Take the top `CONTACTS_TOP_N` (default 10).

Dispatch `job-contact-finder` agents in waves of ≤6 (so top-10 splits into one wave of 6 + one wave of 4). Each agent processes one job.

Per-job dispatch prompt:

```
Find recruiter/hiring-manager contacts for this job.

Job record: <RUN_DIR>/scored_jobs.json (entry index <i>)
Company: <company>
Listing URL: <url>
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/_contacts/<job_slug>.json

Fetch the listing page, then walk the fallback chain: named recruiter on
posting -> company careers page -> LinkedIn search for "<company> recruiter"
-> generic email patterns (careers@, jobs@, talent@, hr@ + domain) ->
company contact form.

Filter out noreply@, no-reply@, mailer-daemon@, donotreply@.

Emit the contacts object with named_recruiter (if found), careers_page_email,
linkedin_company, generic_pattern_guesses, apply_url, confidence, and notes.
```

After all contact-finders return:

1. Read each `_contacts/<job_slug>.json`.
1. Merge into the corresponding `scored_jobs.json` entry as a `contacts` field.
1. Delete `_contacts/` temp dir.

Update `state.md` `Phase` to `contacts_complete`.

______________________________________________________________________

## Phase 7: Cover letters (top-N)

Read `scored_jobs.json`. Take the top `LETTERS_TOP_N` (default 10).

Dispatch `job-letter-writer` agents in waves of ≤6 (one wave of 6 + one wave of 4 for the default top-10).

Per-job dispatch prompt:

```
Write a cover letter for this job.

CV path: <CV_PATH>
Job record: <RUN_DIR>/scored_jobs.json (entry index <i>)
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/letters/<job_slug>.md

Letter must be under 200 words, directly reference details from the
listing, ground every claim in the CV (never fabricate experience), and
avoid AI clichés ("excited to apply", "passionate", "leverage",
"synergy", "in today's fast-paced world").

Include a subject line, the "Dear ...," salutation, and a gratitude-leaning
sign-off, all per the agent playbook. Use plain ASCII punctuation only - no
em-dashes, en-dashes, curly quotes, or ellipsis characters.

Use the front-matter wrapper format specified in the agent playbook;
the body is plain text.
```

After all letter-writers return:

1. Verify each `letters/<job_slug>.md` exists and is non-empty.
1. Search every letter for AI-artifact punctuation: `grep -lP "[\x{2013}\x{2014}\x{2018}\x{2019}\x{201C}\x{201D}\x{2026}]" "<RUN_DIR>"/letters/*.md`. For each hit, re-dispatch that one `job-letter-writer` once with a "replace em-dashes/en-dashes/curly-quotes/ellipsis with ASCII, change nothing else" instruction. If artifacts persist, append an `Errors:` line to `state.md` and continue.
1. Spot-check 2 letters via Read for: word count under 200, a subject line, the salutation, a gratitude sign-off, and no banned cliché phrases. If a letter fails the check, append an `Errors:` line to `state.md` but continue (the report links to it regardless).

Update `state.md` `Phase` to `letters_complete`.

______________________________________________________________________

## Phase 8: Master report

Dispatch `job-reporter`:

```
Write the master job-search report.

Scored jobs: <RUN_DIR>/scored_jobs.json
Excluded jobs: <RUN_DIR>/scored_jobs_excluded.json
Letters directory: <RUN_DIR>/letters/
Strategy file: <RUN_DIR>/search_strategy.json
Original preferences: "<PREFERENCES>"
CV path: <CV_PATH>
Sources file: <RUN_DIR>/sources.json
Output: <RUN_DIR>/<YYYY_MM_DD>_job_search_<slug>.md

Report naming convention: <YYYY_MM_DD>_job_search_<slug>[_vN].md
(append _v2, _v3 if same base name exists).
```

After the reporter completes:

1. Update `state.md` — set `Phase` to `complete`, `Status: complete`, `phase_complete: true`, `what_remains: []`, and add `CompletedAt: <ISO timestamp>`.

1. **Write source-yield history** for next-run demotion logic. Group `scored_jobs.json` entries by `source` (a listing's `source` may be a list when fingerprint-deduped — count each source once per listing). For each source, count how many of its listings ended up in the top-N of `scored_jobs.json` (`top_n_hits`). Also gather `primary_hits` and `alias_hits` from each scout's `_scout_notes` record (preserved in `state.md` Errors or `sources.json` if not stored elsewhere — fall back to `0` when unknown).

   Update `<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json`:

   ```bash
   mkdir -p "<PROJECT_ROOT>/.mz/outreach/_history"
   # Initialize empty if missing.
   [ -f "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json" ] || echo '{}' > "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json"
   ```

   For each source contributing to this run, append a record to `data[cv_hash][source_name].runs`:

   ```json
   { "run_date": "<YYYY-MM-DD>", "top_n_hits": <int>, "primary_hits": <int>, "alias_hits": <int> }
   ```

   Trim each `runs` array to the most recent **3 entries** (older runs are dropped). Write the merged JSON back. Use `jq` to update atomically:

   ```bash
   jq --arg cv "<cv_hash>" --arg src "<source_name>" \
      --argjson rec '{"run_date":"<YYYY-MM-DD>","top_n_hits":<n>,"primary_hits":<n>,"alias_hits":<n>}' \
      '.[$cv][$src].runs = (((.[$cv][$src].runs // []) + [$rec])[-3:])' \
      "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json" > "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json.tmp" \
     && mv "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json.tmp" "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json"
   ```

   Repeat the `jq` call once per source from this run.

1. Display to the user the verification block from `SKILL.md` §Verification:

   - Run name
   - Listings scraped, listings excluded by location, total ranked
   - Top-1 final score
   - Count of cover letters written
   - Absolute path to the master report
