#!/usr/bin/env bash
set -euo pipefail

# CLI helper invoked by the /memory-note skill. Appends a single timestamped
# entry to the Pinned section of project memory. Idempotent on (date, body).
#
# Usage: memory-note.sh "the note body"
#        memory-note.sh --log "background activity entry"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_FILE="${PROJECT_DIR}/.mz/memory/MEMORY.md"
MAX_LOG_LINES=200

TARGET="pinned"
if [[ "${1:-}" == "--log" ]]; then
  TARGET="log"
  shift
fi

BODY="${*:-}"
if [[ -z "$BODY" ]]; then
  echo "memory-note.sh: missing note body" >&2
  exit 2
fi

ensure_memory_file "$MEMORY_FILE"

TODAY=$(date +%Y-%m-%d)
ENTRY="- [${TODAY}] ${BODY}"
ENTRY=$(printf '%s' "$ENTRY" | strip_private)

if grep -qF "$ENTRY" "$MEMORY_FILE" 2>/dev/null; then
  echo "memory-note.sh: identical entry already present, skipping" >&2
  exit 0
fi

if [[ "$TARGET" == "log" ]]; then
  printf '%s\n' "$ENTRY" | prepend_to_log "$MEMORY_FILE" "$MAX_LOG_LINES"
else
  printf '%s\n' "$ENTRY" | prepend_to_pinned "$MEMORY_FILE"
fi

printf 'Wrote to %s section: %s\n' "$TARGET" "$ENTRY"
exit 0
