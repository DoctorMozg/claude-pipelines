#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repo and HOME is, so without this the skill's .mz/ root resolves to HOME.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

# An unfinished search: state exists but scoring never ran, so scored.json is absent and the run must not count.
task=.mz/task/2026_10_30_freelance_search_go_backend
run=.mz/outreach/2026_10_30_freelance_search_go_backend
mkdir -p "$task" "$run"
cat >"$task/state.md" <<'STATE'
schema_version: 2
Status: running
Phase: strategy_approved
Started: 2026-10-30T09:00:00Z
phase_complete: false
what_remains: []
Preferences: Go backend gigs, EU remote
CV path: cv.md
Region scope: EU
RunName: 2026_10_30_freelance_search_go_backend
STATE
cat >"$run/search_strategy.json" <<'JSON'
{
  "derived_from_cv": { "discipline": "engineering" },
  "preferences": { "engagement_types": ["project_gig"], "regions_allowed": ["EU"] }
}
JSON
