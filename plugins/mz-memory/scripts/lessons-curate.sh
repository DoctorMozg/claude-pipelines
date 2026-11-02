#!/usr/bin/env bash
set -euo pipefail

# Background lessons curation, detached by memory-capture.sh at SessionEnd. The curator model
# proposes operations by ID and lib/curator.sh applies them; any failure leaves only eviction.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${SCRIPT_DIR}/lib/lessons.sh"
# shellcheck source=lib/curator.sh
source "${SCRIPT_DIR}/lib/curator.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
LESSONS_FILE="${MEMORY_DIR}/lessons.md"
OPS_LOG="${MEMORY_DIR}/lessons.ops.jsonl"
LOCK_DIR="${MEMORY_DIR}/.curate.lock"
# Well past the child's timeout, so only a run that was killed leaves a lock this old.
STALE_LOCK_MINUTES=10

[[ -f "$LESSONS_FILE" ]] || exit 0
TODAY=$(date +%Y-%m-%d)

if [[ -d "$LOCK_DIR" ]] && [[ -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin "+${STALE_LOCK_MINUTES}" 2>/dev/null)" ]]; then
  rmdir "$LOCK_DIR" 2>/dev/null || true
fi
mkdir "$LOCK_DIR" 2>/dev/null || exit 0
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

log_event() {
  jq -cn --arg date "$TODAY" --arg event "$1" --arg why "$2" '{date: $date, event: $event, why: $why}' \
    >>"$OPS_LOG" 2>/dev/null || true
}

if ! curator_enabled; then
  enforce_lessons_cap "$LESSONS_FILE" "$TODAY"
  exit 0
fi

# The mark comes from the snapshot the model sees; items added during the call wait for the next run.
HIGH=$(inbox_high_id "$LESSONS_FILE")
if OPS=$(lessons_curator_prompt "$LESSONS_FILE" | curator_call "$(lessons_curator_schema)" "$(lessons_curator_system)"); then
  apply_curator_ops "$LESSONS_FILE" "$OPS" "$TODAY" || log_event failed "could not apply the curator operations"
else
  log_event failed "curator call failed or returned no operations"
fi
# Marked even on failure, so a broken setup costs one run per batch of new lessons, not one per session.
mark_lessons_curated "$LESSONS_FILE" "$HIGH"
enforce_lessons_cap "$LESSONS_FILE" "$TODAY"

exit 0
