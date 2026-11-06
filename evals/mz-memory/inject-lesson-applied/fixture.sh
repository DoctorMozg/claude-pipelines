#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
# n=4 reaches the promotion threshold of 3; the inbox item checks that new lessons ride along unreviewed.
write_lessons \
  "- [L-0001] n=4 last=2026-10-28 trig=review src=2026_10_28_build_orders_index@4f2a9c1 tags=migrations :: WHEN adding a database migration → name it db/migrations/MIG-<YYYYMMDD>-<slug>.sql — WHY the deploy runner applies only files whose names start with MIG-" \
  "- [I-0001] 2026-11-01 trig=failure src=2026_11_01_debug_ci status=failed :: WHEN CI times out → rerun it with --shard 4 — WHY the default shard count overloads the runners"
