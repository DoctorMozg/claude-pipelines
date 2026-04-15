#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook (once: true) — injects .mz/memory/MEMORY.md into context.
# Shared inject_memory() function is also sourced by memory-reinject.sh.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"

MAX_LINES=200
MAX_CHARS=8000

inject_memory() {
  local event_name="${1:-SessionStart}"
  local prefix="${2:-Project memory}"

  if [[ ! -f "$MEMORY_FILE" ]] || [[ ! -s "$MEMORY_FILE" ]]; then
    return 1
  fi

  local content
  content=$(head -n "$MAX_LINES" "$MEMORY_FILE")

  if [[ ${#content} -gt $MAX_CHARS ]]; then
    content="${content:0:$MAX_CHARS}
...[memory truncated]"
  fi

  jq -n --arg event "$event_name" --arg prefix "$prefix" --arg content "$content" \
    '{hookSpecificOutput: {hookEventName: $event, additionalContext: ($prefix + " (.mz/memory/MEMORY.md):\n" + $content)}}'
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ ! -f "$MEMORY_FILE" ]]; then
    mkdir -p "$MEMORY_DIR"
    cat > "$MEMORY_FILE" <<'SEED'
# Project Memory

<!-- Entries below are auto-managed by mz-memory. Most recent first. -->
SEED
    echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Project memory initialized at .mz/memory/MEMORY.md (empty). Memory will accumulate as tasks complete."}}'
    exit 0
  fi

  inject_memory "SessionStart" "Project memory" || true
  exit 0
fi
