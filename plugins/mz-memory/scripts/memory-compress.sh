#!/usr/bin/env bash
set -euo pipefail

# Background compression — replaces the bottom half of the Activity Log with
# an LLM-generated summary when the log exceeds COMPRESS_THRESHOLD entries.
# Detached from SessionEnd by memory-capture.sh; runs only when:
#   - MZ_MEMORY_COMPRESS=1
#   - `claude` CLI is on PATH
#   - .mz/memory/.compress.lock is not held
#
# Failure modes are silent: this is a nice-to-have, never block real work.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
LOCK_FILE="${MEMORY_DIR}/.compress.lock"

KEEP_RECENT=100
COMPRESS_THRESHOLD=300
LLM_TIMEOUT=120

[[ -f "$MEMORY_FILE" ]] || exit 0
command -v claude >/dev/null 2>&1 || exit 0

# Best-effort lock — first writer wins, others bail. mkdir is atomic.
if ! mkdir "$LOCK_FILE" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK_FILE" 2>/dev/null || true' EXIT

LOG=$(extract_log "$MEMORY_FILE" 9999)
TOTAL=$(printf '%s\n' "$LOG" | grep -cE '^- ' || true)
[[ "${TOTAL:-0}" -gt "$COMPRESS_THRESHOLD" ]] || exit 0

# Split: keep most-recent KEEP_RECENT entries verbatim, summarize the rest.
RECENT=$(printf '%s\n' "$LOG" | head -n "$KEEP_RECENT")
OLD=$(printf '%s\n' "$LOG" | tail -n "+$((KEEP_RECENT + 1))")
[[ -n "$OLD" ]] || exit 0

PROMPT='Compress this Activity Log into a dense knowledge summary. Output 10-25 markdown bullets grouped by theme (e.g. "## Recurring decisions", "## Resolved bugs", "## Conventions established"). Preserve dates and identifiers verbatim. No preamble. No conclusion.'

SUMMARY=$(printf '%s\n\n---\n\n%s' "$PROMPT" "$OLD" \
  | timeout "$LLM_TIMEOUT" claude -p --output-format text 2>/dev/null || true)

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
