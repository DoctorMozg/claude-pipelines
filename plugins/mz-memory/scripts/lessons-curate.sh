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

[[ -f "$LESSONS_FILE" ]] || exit 0
TODAY=$(date +%Y-%m-%d)

take_run_lock "$LOCK_DIR" || exit 0
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if ! curator_enabled; then
  enforce_lessons_cap "$LESSONS_FILE" "$TODAY"
  exit 0
fi

# The mark comes from the snapshot the model sees; items added during the call wait for the next run.
HIGH=$(inbox_high_id "$LESSONS_FILE")
if OPS=$(lessons_curator_prompt "$LESSONS_FILE" | curator_call "$(curator_schema)" "$(lessons_curator_system)"); then
  apply_curator_ops "$LESSONS_FILE" "$OPS" "$TODAY" || curator_event "$OPS_LOG" failed "could not apply the curator operations"
else
  curator_event "$OPS_LOG" failed "curator call failed or returned no operations"
fi
# Marked even on failure, so a broken setup costs one run per batch of new lessons, not one per session.
mark_lessons_curated "$LESSONS_FILE" "$HIGH"
enforce_lessons_cap "$LESSONS_FILE" "$TODAY"

exit 0
