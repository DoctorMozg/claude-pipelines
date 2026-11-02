#!/usr/bin/env bash
set -euo pipefail

# UserPromptSubmit hook — selectively injects memory entries that match
# keywords from the user's prompt. Pinned section is always included (small,
# high-signal). Lessons, Digest items and Activity Log entries are filtered to
# those containing at least one prompt keyword (>=4 chars, alphanumeric).
# A prompt that corrects Claude also gets a one-line reminder to record the lesson.
#
# Output: hookSpecificOutput with additionalContext when anything applies; the no-op path prints nothing.
# Hard budget: <100ms typical, never blocks the prompt.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${SCRIPT_DIR}/lib/lessons.sh"
command -v jq >/dev/null 2>&1 || exit 0

PROJECT_DIR=$(find_project_root)
MEMORY_FILE="${PROJECT_DIR}/.mz/memory/MEMORY.md"
LESSONS_FILE="${PROJECT_DIR}/.mz/memory/lessons.md"

MAX_MATCHES=15
MAX_LESSONS=5
LESSONS_CHARS=1500
MAX_CHARS=4000
MIN_KEYWORD_LEN=4
# Corrections come first in a message; a log pasted further down that quotes "you forgot" stays quiet.
CORRECTION_SCAN_CHARS=500
NUDGE='If this corrects something you did, fix it, then save the lesson with /memory-note --lesson "WHEN … → … — WHY …".'
# Phrases that push back on what Claude did. Plain instructions such as "don't search the files"
# or "must never call X" are not corrections. Word edges are spelled out: BSD grep lacks \b.
CORRECTION_RE="^(no[,.!]|no\$|nope([^a-z]|\$)|wrong([^a-z]|\$))"
CORRECTION_RE+="|(^|[^a-z])(you (broke|forgot|missed|ignored|skipped|deleted|removed|overwrote|misread|misunderstood)"
CORRECTION_RE+="|(i|we) (told|asked) you|you (should|shouldn't|should not) have"
CORRECTION_RE+="|that('s| is| was) (wrong|incorrect|not right|not what i (asked|wanted|meant))"
CORRECTION_RE+="|why did you|(stop|quit) (doing|adding|changing|using|making)"
CORRECTION_RE+="|(revert|undo) (that|this|it|your)|don't do that again)([^a-z]|\$)"

[[ -f "$MEMORY_FILE" ]] || exit 0

INPUT=""
if [[ ! -t 0 ]]; then
  INPUT=$(cat || true)
fi
[[ -n "$INPUT" ]] || exit 0

PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
[[ -n "$PROMPT" ]] || exit 0

# Slash commands are Claude Code's own syntax, not a reply to Claude.
is_correction() {
  [[ "$PROMPT" != /* ]] || return 1
  local opening
  opening=$(printf '%s\n' "${PROMPT:0:$CORRECTION_SCAN_CHARS}" | sed "s/’/'/g" | tr '[:upper:]' '[:lower:]')
  grep -qE "$CORRECTION_RE" <<<"$opening"
}

NUDGE_LINE=""
if is_correction; then NUDGE_LINE="$NUDGE"; fi

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
  | head -n 12 || true)

[[ -n "$KEYWORDS" || -n "$NUDGE_LINE" ]] || exit 0

PINNED=$(extract_pinned "$MEMORY_FILE" | sed '/^[[:space:]]*$/d')
LESSONS=""
MATCHES=""
if [[ -n "$KEYWORDS" ]]; then
  LESSONS=$(match_lessons "$LESSONS_FILE" "$KEYWORDS" "$MAX_LESSONS" | compact_items | fit_chars "$LESSONS_CHARS")
  PATTERN=$(printf '%s' "$KEYWORDS" | paste -sd '|' -)
  # Digest items lose their metadata before matching, so src=mz-compressed never matches "compressed".
  MATCHES=$(
    {
      extract_digest "$MEMORY_FILE" | compact_items
      extract_log "$MEMORY_FILE" 9999
    } | grep -iE "$PATTERN" 2>/dev/null | head -n "$MAX_MATCHES" || true
  )
fi

if [[ -z "$NUDGE_LINE" && -z "$PINNED" && -z "$LESSONS" && -z "$MATCHES" ]]; then
  exit 0
fi

# The nudge goes right after the header, where the MAX_CHARS cut can't reach it.
PAYLOAD="Project memory matches for this prompt (.mz/memory/MEMORY.md):
"
if [[ -n "$NUDGE_LINE" ]]; then
  PAYLOAD="${PAYLOAD}
${NUDGE_LINE}
"
fi
if [[ -n "$PINNED" ]]; then
  PAYLOAD="${PAYLOAD}
## Pinned
${PINNED}
"
fi
if [[ -n "$LESSONS" ]]; then
  PAYLOAD="${PAYLOAD}
## Matched lessons (.mz/memory/lessons.md)
${LESSONS}
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
