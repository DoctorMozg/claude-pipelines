#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
# n=4 reaches the promotion threshold of 3, so the SessionStart hint names L-0001 and offers /lessons-promote.
write_lessons \
  "- [L-0001] n=4 last=2026-10-28 trig=review src=2026_10_28_build_orders_index@4f2a9c1 tags=migrations :: WHEN adding a database migration → name it db/migrations/MIG-<YYYYMMDD>-<slug>.sql — WHY the deploy runner applies only files whose names start with MIG-" \
  ""
