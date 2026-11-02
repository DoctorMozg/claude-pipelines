# Directory Structure

- **State** — `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`. Source of truth across phases.
- **Card snapshot** — `<PROJECT_ROOT>/.mz/task/<task_name>/card_parsed.json`. Structured extract of the source card, consumed by the deep-enrichment subagents in Phase 2 so they know what is ALREADY documented.
- **Enrichment artifacts** — `<PROJECT_ROOT>/.mz/task/<task_name>/enrichment/<agent_slug>.json`. One JSON per Phase 2 subagent (`news.json`, `tech.json`, `growth.json`, `reputation.json`, `contacts.json`).
- **Briefs** — `<PROJECT_ROOT>/.mz/task/<task_name>/briefs/<contact_slug>.json`. One brief per contact selected for drafting.
- **Profiles** — `<PROJECT_ROOT>/.mz/task/<task_name>/profiles/<contact_slug>.json`. One reader-style read per profiled contact (Social Style or role-priorities, evidence, confidence, calibration directive), written by `outreach-personality-profiler` in Phase 3 and merged into the briefs. Absent when `personality:off`.
- **Drafts** — `<PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md`. One draft file per (contact, channel) pair. Each draft carries YAML frontmatter (`subject`, `channel`, `recipient`) followed by the body.
- **Card lifecycle** — the card ends this run at `target_path = <PROJECT_ROOT>/.mz/outreach/active/<today>_<company_slug>.md`. If `source_path != target_path`, the source file is deleted in the final card-rewrite phase (move semantics). Research-baseline cards at `.mz/outreach/<run>/companies/<slug>.md` and stale-dated active cards (`active/<other-date>_<slug>.md`) are removed by this run.

`task_name` follows `<YYYY_MM_DD>_outreach_enrich_<company_slug>` where `<company_slug>` is derived in Source Resolution (slug without date prefix or `.md`). Same-day collisions append `_v2`, `_v3`.

`<run_dir>` = the run directory `.mz/outreach/<run>/`, that is `dirname(dirname(source_path))`, when the card is still at its research-baseline location `.mz/outreach/<run>/companies/<slug>.md`. Read sender voice and outreach angles from `<run_dir>/strategy.json`. When `source_path` is already an active path, `<run_dir>` falls back to the most-recently-modified `<PROJECT_ROOT>/.mz/outreach/<run>/` directory containing a `strategy.json` (or `default` voice if none can be located).
