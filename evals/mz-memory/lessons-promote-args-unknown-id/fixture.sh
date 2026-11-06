#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
# L-0001 is a valid candidate, so a skill that guesses a neighbour for the missing id would have something to promote.
write_lessons \
  "- [L-0001] n=4 last=2026-10-28 trig=review src=2026_10_28_build_orders_index@4f2a9c1 tags=migrations :: WHEN adding a database migration → name it db/migrations/MIG-<YYYYMMDD>-<slug>.sql — WHY the deploy runner applies only files whose names start with MIG-" \
  ""
printf '# Orders service\n\n## Conventions\n\n- Keep handlers thin; business rules live in services.\n' > CLAUDE.md
