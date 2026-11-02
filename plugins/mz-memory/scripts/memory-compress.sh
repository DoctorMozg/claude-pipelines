#!/usr/bin/env bash
set -euo pipefail

# Background compression: once the Activity Log passes MZ_COMPRESS_THRESHOLD lines, keep the
# newest entries verbatim and replace the rest with an LLM summary. memory-capture.sh starts it
# detached at SessionEnd unless MZ_MEMORY_COMPRESS=0. Failures are silent; it never blocks work.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
LOCK_FILE="${MEMORY_DIR}/.compress.lock"

# In lines, like the MZ_LOG_MAX_LINES cap and MZ_COMPRESS_THRESHOLD in lib/common.sh.
KEEP_RECENT=100
LLM_TIMEOUT=120

[[ -f "$MEMORY_FILE" ]] || exit 0
command -v claude >/dev/null 2>&1 || exit 0

# Best-effort lock — first writer wins, others bail. mkdir is atomic.
if ! mkdir "$LOCK_FILE" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK_FILE" 2>/dev/null || true' EXIT

LOG=$(extract_log "$MEMORY_FILE" 9999)
TOTAL=$(printf '%s\n' "$LOG" | awk 'END { print NR }')
[[ "${TOTAL:-0}" -gt "$MZ_COMPRESS_THRESHOLD" ]] || exit 0

# Keep about KEEP_RECENT lines verbatim, extended to the end of the entry the cut lands in.
RECENT=$(printf '%s\n' "$LOG" | awk -v keep="$KEEP_RECENT" 'NR > keep && /^- / { exit } { print }' || true)
OLD=$(printf '%s\n' "$LOG" | awk -v keep="$KEEP_RECENT" 'NR > keep && /^- / { old = 1 } old { print }')
[[ -n "$OLD" ]] || exit 0

PROMPT='Compress this Activity Log into a dense knowledge summary. Output 10-25 markdown bullets grouped by theme (e.g. "## Recurring decisions", "## Resolved bugs", "## Conventions established"). Preserve dates and identifiers verbatim. No preamble. No conclusion.'

# The child session's own SessionEnd hook must not start another compression.
SUMMARY=$(printf '%s\n\n---\n\n%s' "$PROMPT" "$OLD" \
  | MZ_MEMORY_COMPRESS=0 timeout "$LLM_TIMEOUT" claude -p --output-format text 2>/dev/null || true)

[[ -n "$SUMMARY" ]] || exit 0

# Rewrite the log region: recent entries on top, then a summary fence.
NEW_LOG=$(printf '%s\n\n<!-- mz-compressed -->\n%s\n' "$RECENT" "$SUMMARY")

awk -v start="$MZ_LOG_START" -v end="$MZ_LOG_END" -v new="$NEW_LOG" '
  $0 == start { print; printf "%s\n", new; in_log = 1; next }
  $0 == end { in_log = 0; print; next }
  in_log { next }
  { print }
' "$MEMORY_FILE" | atomic_write "$MEMORY_FILE"

exit 0
