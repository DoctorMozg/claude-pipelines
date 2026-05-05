#!/usr/bin/env bash
set -euo pipefail

# UserPromptSubmit hook — selectively injects memory entries that match
# keywords from the user's prompt. Pinned section is always included (small,
# high-signal). Activity log entries are filtered to those whose line text
# contains at least one prompt keyword (>=4 chars, alphanumeric).
#
# Output schema: hookSpecificOutput with required `additionalContext`.
# Hard budget: <100ms typical, never blocks the prompt.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_FILE="${PROJECT_DIR}/.mz/memory/MEMORY.md"

MAX_MATCHES=15
MAX_CHARS=2000
MIN_KEYWORD_LEN=4

emit_silent() {
  jq -n --arg event "UserPromptSubmit" --arg ctx "" \
    '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}'
  exit 0
}

[[ -f "$MEMORY_FILE" ]] || emit_silent

INPUT=""
if [[ ! -t 0 ]]; then
  INPUT=$(cat || true)
fi
[[ -n "$INPUT" ]] || emit_silent

PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
[[ -n "$PROMPT" ]] || emit_silent

# Normalize: lowercase, strip non-alphanumeric, dedup, drop short words and
# common stopwords. Keep at most 12 keywords to bound the grep cost.
KEYWORDS=$(printf '%s' "$PROMPT" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -c 'a-z0-9' '\n' \
  | awk -v min="$MIN_KEYWORD_LEN" '
      length($0) >= min &&
      $0 !~ /^(this|that|with|from|have|will|been|were|what|when|where|which|would|could|should|about|into|then|than|some|just|like|make|made|much|more|most|other|over|such|them|they|their|there|these|those|your|yours|need|want|please|file|files|code|test|tests)$/ \
      { print }
    ' \
  | awk '!seen[$0]++' \
  | head -n 12)

[[ -n "$KEYWORDS" ]] || emit_silent

PINNED=$(extract_pinned "$MEMORY_FILE" | sed '/^[[:space:]]*$/d')
LOG=$(extract_log "$MEMORY_FILE" 9999)

PATTERN=$(printf '%s' "$KEYWORDS" | paste -sd '|' -)
MATCHES=""
if [[ -n "$LOG" && -n "$PATTERN" ]]; then
  MATCHES=$(printf '%s\n' "$LOG" | grep -iE "$PATTERN" 2>/dev/null | head -n "$MAX_MATCHES" || true)
fi

if [[ -z "$PINNED" && -z "$MATCHES" ]]; then
  emit_silent
fi

PAYLOAD="Project memory matches for this prompt (.mz/memory/MEMORY.md):
"
if [[ -n "$PINNED" ]]; then
  PAYLOAD="${PAYLOAD}
## Pinned
${PINNED}
"
fi
if [[ -n "$MATCHES" ]]; then
  PAYLOAD="${PAYLOAD}
## Matched activity entries
${MATCHES}
"
fi

if [[ ${#PAYLOAD} -gt $MAX_CHARS ]]; then
  PAYLOAD="${PAYLOAD:0:$MAX_CHARS}
...[memory truncated]"
fi

jq -n --arg event "UserPromptSubmit" --arg ctx "$PAYLOAD" \
  '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}'
exit 0
