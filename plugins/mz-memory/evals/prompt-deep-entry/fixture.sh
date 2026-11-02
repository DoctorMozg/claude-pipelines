#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
# 250 short log lines, newest first, so the 200-line cap binds before the 8000-char one. SessionStart
# injects only the newest 200, and entry 240 can reach the model only through the UserPromptSubmit keyword match.
log=""
for i in $(seq 1 250); do
  if [[ "$i" == 240 ]]; then
    line="- [2025-06-01] marmoset-bridge: the staging database listens on port 6543 (ticket OPAL-19)"
  else
    line=$(printf -- '- [2026-%02d-%02d] task %03d done' $(( (i % 9) + 1 )) $(( (i % 27) + 1 )) "$i")
  fi
  log="${log:+$log
}$line"
done
write_memory "- [2026-10-01] Use UTC timestamps everywhere." "$log"
