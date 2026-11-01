#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook: injects project memory on startup, after /clear and after compaction.
# hooks.json skips resume and fork because the reused transcript already holds the memory.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"

MAX_LOG_LINES=200
MAX_CHARS=8000

# Build the payload: pinned section first (always included if non-empty),
# then most-recent activity log entries up to MAX_LOG_LINES, capped at
# MAX_CHARS total. Returns 1 if there's nothing to inject.
build_payload() {
  [[ -f "$MEMORY_FILE" && -s "$MEMORY_FILE" ]] || return 1

  local pinned log payload
  pinned=$(extract_pinned "$MEMORY_FILE" | sed '/^[[:space:]]*$/d')
  log=$(extract_log "$MEMORY_FILE" "$MAX_LOG_LINES")

  payload=""
  if [[ -n "$pinned" ]]; then
    payload="## Pinned"$'\n'"${pinned}"$'\n\n'
  fi
  if [[ -n "$log" ]]; then
    payload="${payload}## Activity Log"$'\n'"${log}"
  fi
  [[ -n "$payload" ]] || return 1

  if [[ ${#payload} -gt $MAX_CHARS ]]; then
    payload="${payload:0:$MAX_CHARS}
...[memory truncated]"
  fi
  printf '%s' "$payload"
}

emit_context() {
  jq -n --arg payload "$1" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $payload}}'
}

ensure_memory_file "$MEMORY_FILE"

if body=$(build_payload); then
  emit_context "Project memory (.mz/memory/MEMORY.md):
${body}"
else
  emit_context "Project memory initialized at .mz/memory/MEMORY.md (empty). Memory accumulates as tasks complete."
fi
exit 0
