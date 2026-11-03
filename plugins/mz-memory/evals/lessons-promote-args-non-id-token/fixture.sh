#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
# Two migration lessons make "the migrations one" ambiguous, so only asking is right and a guess is visible.
curated=$(
  cat <<'LESSONS'
- [L-0001] n=4 last=2026-10-28 trig=review src=2026_10_28_build_orders_index@4f2a9c1 tags=migrations :: WHEN adding a database migration → name it db/migrations/MIG-<YYYYMMDD>-<slug>.sql — WHY the deploy runner applies only files whose names start with MIG-
- [L-0002] n=3 last=2026-10-22 trig=failure src=2026_10_22_debug_rollout@b83c5a0 tags=migrations :: WHEN a migration drops or renames a column → ship the backward-compatible step first and the drop in a later release — WHY the previous release still reads the old column during a rolling deploy
LESSONS
)
write_lessons "$curated" ""
printf '# Orders service\n\n## Conventions\n\n- Keep handlers thin; business rules live in services.\n' > CLAUDE.md
