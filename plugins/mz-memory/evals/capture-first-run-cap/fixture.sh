#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "" ""
# 60 completed tasks and no .last-capture marker: the first capture reads only the 50 newest.
for i in $(seq -w 1 60); do
  printf '## Notes\n- item %s\n' "$i" | write_task "2026_10_01_build_item_$i" complete
done
