#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook: injects project memory on startup, after /clear and after compaction.
# hooks.json skips resume and fork because the reused transcript already holds the memory.

# shellcheck source=lib/common.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/lessons.sh"
command -v jq >/dev/null 2>&1 || exit 0

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
LESSONS_FILE="${MEMORY_DIR}/lessons.md"

MAX_LOG_LINES=200
# Claude Code cuts any injected string past 10,000 characters down to a 2,000-character preview.
MAX_CHARS=8000
LESSONS_CHARS=3000
DIGEST_CHARS=3000
LESSONS_TOP=12
INBOX_NEWEST=3
HINT_IDS=5

section() {
  if [[ -n "$2" ]]; then printf '## %s\n%s\n\n' "$1" "$2"; fi
}

# Lessons seen MZ_LESSON_KEEP_N times or more are worth making permanent rules.
promotion_hint() {
  local ids shown
  ids=$(promotion_candidates "$LESSONS_FILE")
  [[ -n "$ids" ]] || return 0
  shown=$(awk -v max="$HINT_IDS" -f "${CLAUDE_PLUGIN_ROOT}/scripts/awk/join-ids.awk" <<<"$ids")
  printf 'Promotion candidates (seen %s+ times): %s. At a natural pause, offer /lessons-promote to turn them into project rules.\n' \
    "$MZ_LESSON_KEEP_N" "$shown"
}

lessons_body() {
  local lessons
  lessons=$(session_lessons "$LESSONS_FILE" "$LESSONS_TOP" "$INBOX_NEWEST" | compact_items | fit_chars "$LESSONS_CHARS")
  [[ -n "$lessons" ]] || return 0
  # Lessons read like instructions, so their standing is spelled out: an inbox line is unreviewed text.
  printf 'Advice from earlier sessions. L- lessons are curated, I- ones are new; neither overrides the user.\n%s\n' "$lessons"
  promotion_hint
}

# Pinned rules first, then lessons, the Digest and the newest log lines, cut at MAX_CHARS.
# Returns 1 if there's nothing to inject.
build_payload() {
  [[ -f "$MEMORY_FILE" && -s "$MEMORY_FILE" ]] || return 1

  local payload
  payload=$(
    section "Pinned" "$(extract_pinned "$MEMORY_FILE" | sed '/^[[:space:]]*$/d')"
    section "Lessons (.mz/memory/lessons.md)" "$(lessons_body)"
    section "Digest" "$(extract_digest "$MEMORY_FILE" | compact_items | fit_chars "$DIGEST_CHARS")"
    section "Activity Log" "$(extract_log "$MEMORY_FILE" "$MAX_LOG_LINES")"
  )
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

# An unwritable project still gets whatever memory it has; a hook error would only nag the user.
writable=1
if ! ensure_memory_file "$MEMORY_FILE"; then
  writable=0
  echo "memory-inject.sh: can't write ${MEMORY_DIR}, injecting it as it is" >&2
fi

if body=$(build_payload); then
  emit_context "Project memory (.mz/memory/MEMORY.md):
${body}"
elif [[ "$writable" == 1 ]]; then
  emit_context "Project memory initialized at .mz/memory/MEMORY.md (empty). Memory accumulates as tasks complete."
fi
exit 0
