#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
# n=2 sits just under the promotion threshold of 3, so a default run has nothing to offer.
curated=$(
  cat <<'EOF'
- [L-0001] n=2 last=2026-10-28 trig=review src=2026_10_28_build_orders_index@4f2a9c1 tags=migrations :: WHEN adding a database migration → name it db/migrations/MIG-<YYYYMMDD>-<slug>.sql — WHY the deploy runner applies only files whose names start with MIG-
- [L-0002] n=1 last=2026-10-20 trig=failure src=2026_10_20_debug_ci@7d1e0b3 tags=ci :: WHEN CI times out → rerun it with --shard 4 — WHY the default shard count overloads the runners
EOF
)
write_lessons "$curated" ""
printf '# Orders service\n\n## Conventions\n\n- Keep handlers thin; business rules live in services.\n' > CLAUDE.md
