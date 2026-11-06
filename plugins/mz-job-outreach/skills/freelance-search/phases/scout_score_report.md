# Phases 3-6: Scout, Filter, Pre-score, Score, Report

## Phase 3: Scout fan-out

Read `<RUN_DIR>/sources.json`. Split into two lists:

- `scrape_sources` — entries with `scrape_allowed: true`. Dispatched to scouts.
- `guidance_sources` — entries with `scrape_allowed: false`. Skipped now; rendered as DOC-ONLY cards in Phase 6.

Set per-source cap: `ceil(limit / scrape_source_count)`, minimum 5, maximum 12.

Before each wave of two or more scouts, emit the pre-dispatch manifest. When the sources need several waves, number them (for example "wave 2 of 3") and pass each role label as the agent's `description`:

```
Dispatching freelance scouts, wave <w> of <K> — <N> agents in parallel
Purpose: extract gig listings from <N> sources
- freelance-scout — <source name>
- freelance-scout — <source name>
```

Dispatch one `freelance-scout` per `scrape_sources` entry in parallel waves of up to 6 concurrent agents:

```
Extract freelance gig listings from <SOURCE_NAME>.

Source: <full JSON record from sources.json>
Strategy file: <RUN_DIR>/search_strategy.json
Recency window (days): <RECENCY_DAYS>
Per-source cap: <PER_SOURCE_CAP>
Output file: <RUN_DIR>/_scout/<source_slug>.json

Construct 3+ primary query variants per top freelance title using
search_queries and (when source.language_hint matches a key in
bilingual_query_variants) language-matched variants. Paginate up to 10 pages
or until cap reached.

If primary queries return < 5 unique URLs and title_aliases exists, fall
back to alias queries (max 4 per title).

Extract per-gig metadata (title, client_name_or_handle, location_string,
remote_status_raw, url, posted_date, budget_range_raw, engagement_duration,
project_scope_raw — up to 800 chars verbatim, summary_snippet,
application_method_raw, application_deadline_raw, language_of_listing,
domain_or_industry, source). Run the lexical engagement-type tagger to
emit candidate_engagement_types.

End with a _scout_notes record summarizing queries, language used, and
expansion details.
```

Wait for all scouts to complete. Append `Errors:` bullets in `state.md` for any non-DONE statuses.

Once every scout of a wave has reported, emit the post-wave rollup before the next wave:

```
Wave complete (wave <w> of <K>) — <returned>/<dispatched> agents returned
- freelance-scout (<source name>): <STATUS> — <summary, ≤8 words>
```

A scout that returns no `STATUS:` line is listed as `NO RETURN BLOCK` and counted as not returned.

Update `state.md` `Phase` to `scouts_complete`.

______________________________________________________________________

## Phase 4: Normalize + filter

Read every `_scout/<source>.json`. For each gig:

1. **Drop `_scout_notes`** entries — they are summaries, not gigs.
1. **Dedup by URL** across all scout outputs. Prefer the entry with the most non-null metadata.
1. **Filter by `candidate_engagement_types`** — keep gigs whose `candidate_engagement_types` intersects with `preferences.engagement_types`. Gigs with empty `candidate_engagement_types` are kept (ambiguous — scorer will handle).
1. **Filter by recency** — drop gigs whose parsed `posted_date` is older than `recency_window_days × 1.5`. Gigs with `null` or unparseable `posted_date` are kept (with a `posted_date_unparseable: true` flag for the scorer).
1. **Filter by region** — apply `location_eligibility_rule` from the strategy. Drop gigs whose `remote_status_raw` explicitly excludes the candidate's region (e.g. "US only" for an EU candidate).
1. **Apply banned-domain check** — refuse any gig whose URL contains `upwork.com`, `fiverr.com`, `peopleperhour.com`, `freelancer.com`, or `guru.com`. If found, halt and emit a bug report — this should never happen given researcher mode-blocklist.
1. **Assign `gig_slug`** — slug each surviving gig's title (lowercase, non-alphanumerics to `-`, max 40 chars) and store it on the record as `gig_slug`, appending `-2`, `-3` on a clash. Phases 4.5 and 5 name one file per gig after it, so two gigs must never share a slug.

Write the surviving array to `<RUN_DIR>/raw_gigs.json`. Write filtered-out gigs with their exclusion reasons to `<RUN_DIR>/scored_excluded.json` for transparency.

Update `state.md` `Phase` to `filter_complete`. Log counts: scraped, deduped, kept after engagement filter, kept after recency filter, kept after region filter, final.

______________________________________________________________________

## Phase 4.5: Cheap pre-score (LLM 0/1/2)

Dispatch `job-prescorer` agents in parallel waves of up to 6 to rate every gig in `raw_gigs.json` against the CV's must-have skills, or-groups and synonym clusters. Gigs rated `0` are dropped before the full score; `1` and `2` advance.

### 4.5.1 Split into prescore batches

Read `<RUN_DIR>/raw_gigs.json`. Compute `batch_count = ceil(len(gigs) / 15)` and write each batch to `<RUN_DIR>/_prescore_batches/batch_<i>.json`, one array of whole gig records per file, so the prescorer sees each gig's `project_scope_raw`.

### 4.5.2 Dispatch prescorers

Prescorers are writer agents: each writes only its own `batch_<i>_rated.json`. Take `<CV_PATH>` from the `CV path` key in `state.md`. Wait for every agent in the wave to report, then check that each rated file exists on disk before using it.

Before each wave of two or more prescorers, emit the pre-dispatch manifest, numbered and with role labels passed as `description` as in Phase 3:

```
Dispatching gig pre-scoring, wave <w> of <K> — <N> agents in parallel
Purpose: rate gigs for must-have skill presence
- job-prescorer — batch <i> of <batch_count>
- job-prescorer — batch <i> of <batch_count>
```

Per-batch dispatch prompt:

```
Pre-score this batch of freelance gigs against the CV's must-have skills.

CV path: <CV_PATH>
Strategy file: <RUN_DIR>/search_strategy.json
Batch file (input): <RUN_DIR>/_prescore_batches/batch_<i>.json
Output file: <RUN_DIR>/_prescore_batches/batch_<i>_rated.json

Read must_have_skills, must_have_or_groups, synonym_clusters, and
nice_to_have_skills from the strategy. Scan each gig's project_scope_raw as
well as its title and summary_snippet. Rate each gig 0/1/2:

  0 = no must-have or or-group matches; clearly off-stack.
  1 = partial match; full scorer should adjudicate.
  2 = every must-have and or-group satisfied (cluster terms count).

Emit one record per input gig with url, rating, matched_must_haves,
matched_or_groups, and a one-phrase reason (≤ 12 words). Recall-biased —
when uncertain, rate 1 not 0.
```

Once every prescorer of a wave has reported, emit the post-wave rollup in the same form as Phase 3, with a `job-prescorer (batch <i>)` line per agent.

A prescorer returns `NEEDS_CONTEXT` when its batch file, the CV or the strategy is unreadable, or the strategy has no `must_have_skills`. Rewrite a missing batch file yourself; for any other gap follow the SKILL.md `Error Handling` rule and ask the user, storing a new CV path as `CV path` in `state.md`. Re-dispatch that batch once. If it returns `NEEDS_CONTEXT` again, list it under `Errors:` in `state.md` and let its gigs advance unrated.

### 4.5.3 Merge and filter

After all prescorers return:

1. Concat `_prescore_batches/batch_*_rated.json` into one array and build a `url → rating` map.
1. Check that the number of ratings equals the number of gigs in `raw_gigs.json`. If not, add a `DONE_WITH_CONCERNS` line under `Errors:` in `state.md` naming the shortfall, and go on with what is present.
1. Partition `raw_gigs.json` by the rating each gig's `url` maps to:
   - `rating == 0` → append to `scored_excluded.json` with `excluded_reason: "prescore_below_threshold"` and `prescore_reason: "<the prescorer's one-phrase reason>"`.
   - `rating ∈ {1, 2}`, or no rating → keep for full scoring with `prescore_rating` on the record (`null` when unrated), since a missing rating is no evidence of a miss.
1. Write the kept gigs to `<RUN_DIR>/prescored_gigs.json`.

Update `state.md` `Phase` to `prescore_complete` and add `PrescoreDropped: <count>`, `PrescoreAdvanced: <count>`.

If `PrescoreAdvanced == 0`, stop before scoring: dispatch no scorer, let Phase 5 write its empty `scored.json`, and go on to Phase 6, which still reports the exclusions and the guidance-only networks.

______________________________________________________________________

## Phase 5: Full score & rank

Before each wave of two or more scorers, emit the pre-dispatch manifest, numbered and with role labels passed as `description` as in Phase 3:

```
Dispatching gig scoring, wave <w> of <K> — <N> agents in parallel
Purpose: score prescore-survivor gigs against the strategy
- freelance-scorer — score gig <gig_slug>
- freelance-scorer — score gig <gig_slug>
```

Dispatch `freelance-scorer` in parallel waves of 6 over the gigs in `prescored_gigs.json`:

```
Score this freelance gig against the strategy.

Gig JSON: <one gig from prescored_gigs.json>
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/_scored/<gig_slug>.json

Apply hard gate (missing must-have = score 0). Score seven axes per
strategy.scoring_weights. Compare budget_fit in the gig's native rate
format; surface conversion math verbatim in score_reason.
```

Once every scorer of a wave has reported, emit the post-wave rollup in the same form as Phase 3, with a `freelance-scorer (<gig_slug>)` line per agent.

Scorers in a wave run at the same time, so each writes only its own `_scored/<gig_slug>.json` and the orchestrator alone writes `scored.json`. After all scorers complete, list any dispatched gig without its file under `Errors:` in `state.md`, then merge the files, sorted by `score` descending and cut to the top `limit`. A scorer record holds only the score and its reasons, so the merge joins each one to its gig in `raw_gigs.json` by `gig_slug`; Phase 6 and `/freelance-pitch` read the gig's own fields from `scored.json`:

```bash
jq -s --slurpfile gigs "<RUN_DIR>/raw_gigs.json" 'INDEX($gigs[0][]; .gig_slug) as $by_slug | map($by_slug[.gig_slug // ""] + .) | sort_by(-.score) | .[:<LIMIT>]' "<RUN_DIR>"/_scored/*.json > "<RUN_DIR>/scored.json"
```

If no gig survived prescoring, write `[]` to `<RUN_DIR>/scored.json` instead.

Update `state.md` `Phase` to `score_complete`.

______________________________________________________________________

## Phase 6: Master report + guidance cards

Read:

- `<RUN_DIR>/scored.json` — sorted top-N.
- `<RUN_DIR>/sources.json` — for guidance entries.
- `<RUN_DIR>/search_strategy.json` — for context blurbs.
- `<RUN_DIR>/scored_excluded.json` — for an "Excluded" summary section.

Generate `<RUN_DIR>/<YYYY_MM_DD>_freelance_search_<slug>.md` with this structure:

```markdown
# Freelance Search Report — <YYYY-MM-DD>

## Summary

- **Region scope**: <region_scope>
- **Discipline**: <strategy.derived_from_cv.discipline> (+ <secondary_disciplines>)
- **Engagement types**: <strategy.preferences.engagement_types>
- **Rate floor**: <rate_floor.hourly_usd>/hr | <rate_floor.daily_usd>/day | <rate_floor.project_total_usd>/project (FX basis: <fx_basis>)
- **Recency window**: <recency_window_days> days
- **Total scraped**: <N>
- **After filters + prescore**: <N>
- **Top score**: <top_score>

## Top-N Gigs

(One section per scored gig, sorted by score descending, top `limit` entries)

### #<rank>. <gig.title> — <gig.client_name_or_handle> [score: <score>/100]

- **Source**: <gig.source>
- **Location**: <gig.location_string> / <gig.remote_status_raw>
- **Posted**: <gig.posted_date>
- **Engagement types detected**: <gig.candidate_engagement_types>
- **Budget**: <gig.budget_range_raw> (or "Not disclosed")
- **Duration**: <gig.engagement_duration> (or "Not disclosed")
- **Apply via**: <gig.application_method_raw>
- **Deadline**: <gig.application_deadline_raw> (or "Open")
- **URL**: <gig.url>

**Scope (verbatim)**: > <gig.project_scope_raw>

**Score reason**: <gig.score_reason>

**Next step**: To generate a proposal for this gig, run `/freelance-pitch <rank>` or `/freelance-pitch <gig.url>`.

______________________________________________________________________

## Guidance-Only Networks

(One card per entry from sources.json where `scrape_allowed == false`. These are referral/invite-only — the pipeline did not scrape them; this section lists them so the user knows the access path.)

### <name> — <region> [<discipline_tags>]

- **URL**: <url>
- **Relevance to your profile**: <relevance_score>/10
- **Access path**: <guidance_note>

______________________________________________________________________

## Excluded (sample)

<count> gigs were filtered out. Top exclusion reasons:
- `prescore_below_threshold`: <N>
- `engagement_type_mismatch`: <N>
- `region_excluded`: <N>
- `recency_expired`: <N>

(Full exclusion list at `<RUN_DIR>/scored_excluded.json`.)

______________________________________________________________________

## Next Steps

- Pick a top gig and run `/freelance-pitch <rank>` to draft a grounded proposal.
- For referral-only networks, follow the access path in the guidance cards above.
- If results are thin, re-run with a wider region scope (`Global`) or a relaxed rate floor.
```

After writing the report, also append a yield-history record to `<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json`:

```bash
# Compute per-source top-N hit counts from scored.json.
# Append a new run record under {cv_hash: {source_name: {runs: [...]}}}.
# Keep only the last 3 runs per source.
```

Use this jq update template per source emitting at least one scored gig:

```bash
top_n_cutoff=<score-rank-50-cutoff-from-this-run>
for source in $(jq -r '[.[].source] | unique[]' "<RUN_DIR>/scored.json"); do
  top_n_hits=$(jq --arg s "$source" --argjson c "$top_n_cutoff" \
    '[.[] | select(.source == $s and .score >= $c)] | length' "<RUN_DIR>/scored.json")
  primary_hits=$(jq --arg s "$source" \
    '[.[] | select(.source == $s)] | length' "<RUN_DIR>/scored.json")
  alias_hits=$(jq --arg s "$source" \
    'reduce .[] as $g (0; if $g.source == $s and ($g._from_alias // false) then . + 1 else . end)' \
    "<RUN_DIR>/scored.json")

  jq --arg cv "<cv_hash>" --arg src "$source" \
     --arg date "$(date -u +%Y-%m-%d)" \
     --argjson tn "$top_n_hits" --argjson ph "$primary_hits" --argjson ah "$alias_hits" '
    .[$cv][$src].runs = (
      [{run_date: $date, top_n_hits: $tn, primary_hits: $ph, alias_hits: $ah}] +
      (.[$cv][$src].runs // []) | .[:3]
    )' "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json" > "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json.tmp" \
    && mv "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json.tmp" "<PROJECT_ROOT>/.mz/outreach/_history/source_quality.json"
done
```

Initialize the history file with `{}` if it does not exist.

Update `state.md` `Phase` to `report_complete`, `Status` to `complete`. Emit verification block per the SKILL.md `Verification` section.
