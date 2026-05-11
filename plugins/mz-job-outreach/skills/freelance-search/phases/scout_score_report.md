# Phases 3-6: Scout, Filter, Pre-score, Score, Report

## Phase 3: Scout fan-out

Read `<RUN_DIR>/sources.json`. Split into two lists:

- `scrape_sources` — entries with `scrape_allowed: true`. Dispatched to scouts.
- `guidance_sources` — entries with `scrape_allowed: false`. Skipped now; rendered as DOC-ONLY cards in Phase 6.

Set per-source cap: `ceil(limit / scrape_source_count)`, minimum 5, maximum 12.

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

Write the surviving array to `<RUN_DIR>/raw_gigs.json`. Write filtered-out gigs with their exclusion reasons to `<RUN_DIR>/scored_excluded.json` for transparency.

Update `state.md` `Phase` to `filter_complete`. Log counts: scraped, deduped, kept after engagement filter, kept after recency filter, kept after region filter, final.

______________________________________________________________________

## Phase 4.5: Cheap pre-score (LLM 0/1/2)

Dispatch `job-prescorer` (reused as-is, format-agnostic skill matcher) in parallel waves of 6:

```
Pre-score the gig for must-have skill presence.

Gig JSON: <one gig from raw_gigs.json>
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/_prescored/<gig_slug>.json

Scan title + project_scope_raw + summary_snippet for must-have skills using
synonym_clusters. Emit 0 (no must-haves found), 1 (some must-haves), or 2
(all must-haves found).
```

Keep only gigs with prescore ≥ 1. Drop the rest into `scored_excluded.json` with `excluded_reason: "prescore_below_threshold"`.

Update `state.md` `Phase` to `prescore_complete`.

______________________________________________________________________

## Phase 5: Full score & rank

Dispatch `freelance-scorer` in parallel waves of 6 over the prescore-survivors:

```
Score this freelance gig against the strategy.

Gig JSON: <one gig from prescore-survivor set>
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/scored.json (append)

Apply hard gate (missing must-have = score 0). Score seven axes per
strategy.scoring_weights. Compare budget_fit in the gig's native rate
format; surface conversion math verbatim in score_reason.
```

After all scorers complete, read `<RUN_DIR>/scored.json`, sort by `score` descending, take top-`limit` entries, and write the sorted array back.

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

After writing the report, also append a yield-history record to `.mz/outreach/_history/source_quality.json`:

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
    )' .mz/outreach/_history/source_quality.json > /tmp/sq.json
  mv /tmp/sq.json .mz/outreach/_history/source_quality.json
done
```

Initialize the history file with `{}` if it does not exist.

Update `state.md` `Phase` to `report_complete`, `Status` to `complete`. Emit verification block per the SKILL.md `Verification` section.
