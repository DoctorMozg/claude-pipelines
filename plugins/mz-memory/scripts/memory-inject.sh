#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook (once: true) — injects project memory into context.
# Shared inject_memory() is also sourced by memory-reinject.sh and
# memory-prompt-inject.sh.

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

inject_memory() {
  local event_name="${1:-SessionStart}"
  local prefix="${2:-Project memory}"

  local body
  body=$(build_payload) || return 1

  local payload="${prefix} (.mz/memory/MEMORY.md):
${body}"

  # PreCompact + PostCompact reject hookSpecificOutput per the validator.
  # Stdout is read as additional context for those events.
  if [[ "$event_name" == "PostCompact" || "$event_name" == "PreCompact" ]]; then
    printf '%s\n' "$payload"
  else
    jq -n --arg event "$event_name" --arg payload "$payload" \
      '{hookSpecificOutput: {hookEventName: $event, additionalContext: $payload}}'
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  ensure_memory_file "$MEMORY_FILE"

  if ! inject_memory "SessionStart" "Project memory"; then
    jq -n --arg event "SessionStart" --arg payload \
      "Project memory initialized at .mz/memory/MEMORY.md (empty). Memory accumulates as tasks complete." \
      '{hookSpecificOutput: {hookEventName: $event, additionalContext: $payload}}'
  fi
  exit 0
fi
