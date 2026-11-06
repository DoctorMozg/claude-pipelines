#!/usr/bin/env bash
set -euo pipefail
# Bash 4.4+ keeps errexit inside $(...), as the capture hook has it; on 3.2 only the Inbox write is checked.
shopt -s inherit_errexit 2>/dev/null || true

# CLI helper invoked by the /memory-note skill. A note goes to Pinned, or to the Activity Log with
# --log; a lesson goes to the lessons Inbox with --lesson. Saving the same text twice a day is a no-op.
#
# Usage: memory-note.sh "the note body"
#        memory-note.sh --log "background activity entry"
#        memory-note.sh --lesson "WHEN … → … — WHY …"

# Hooks get CLAUDE_PLUGIN_ROOT (PLUGIN_ROOT under Codex); a skill's Bash call gets neither, so set both.
PLUGIN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CLAUDE_PLUGIN_ROOT=$PLUGIN_ROOT
# shellcheck source=lib/common.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/lessons.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_FILE="${PROJECT_DIR}/.mz/memory/MEMORY.md"
LESSONS_FILE="${PROJECT_DIR}/.mz/memory/lessons.md"
# The prompt hook asks for a lesson when the user corrects Claude; a leading (review) etc. overrides it.
LESSON_TRIGGER="correction"
# A saved lesson has no task behind it, so it carries this instead of the task's Status.
LESSON_STATUS="noted"

fail() {
  echo "memory-note.sh: $1" >&2
  exit 2
}

# save_note <pinned|log> <body> — write "- [date] body" unless that exact line is already there.
save_note() {
  local target="$1" entry="- [${TODAY}] $2"
  ensure_memory_file "$MEMORY_FILE"
  if grep -qxF -e "$entry" "$MEMORY_FILE"; then
    echo "memory-note.sh: identical entry already present, skipping" >&2
    return 0
  fi
  if [[ "$target" == "log" ]]; then
    printf '%s\n' "$entry" | prepend_to_log "$MEMORY_FILE" "$MZ_LOG_MAX_LINES"
  else
    printf '%s\n' "$entry" | prepend_to_pinned "$MEMORY_FILE"
  fi
  printf 'Wrote to %s section: %s\n' "$target" "$entry"
}

# save_lesson <text> — add the lesson to the Inbox as the dated memory-note task of today.
save_lesson() {
  local text="$1"
  local length task sha written
  # Measured with the awk the store uses, so a lesson that passes here is never cut short there.
  length=$(printf '%s\n' "$text" | awk '{ print length($0) }')
  if [[ "$length" -gt "$MZ_LESSON_MAX_CHARS" ]]; then
    fail "the lesson is over ${MZ_LESSON_MAX_CHARS} characters; shorten it"
  fi

  task="${TODAY//-/_}_memory-note"
  sha=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || true)
  # A plain assignment, not an if: a failure inside must stop the script, or it reads as a duplicate.
  written=$(printf '%s%s%s%s%s\n' "$task" "$MZ_LESSON_FS" "$LESSON_STATUS" "$MZ_LESSON_FS" "$text" \
    | add_lessons_to_inbox "$LESSONS_FILE" "$TODAY" "$sha" "$LESSON_TRIGGER")
  if [[ -z "$written" ]]; then
    echo "memory-note.sh: this lesson was already saved today, skipping" >&2
    return 0
  fi
  printf 'Wrote to lessons inbox: %s\n' "$written"
}

TARGET="pinned"
case "${1:-}" in
  --log)
    TARGET="log"
    shift
    ;;
  --lesson)
    TARGET="lesson"
    shift
    ;;
esac
if [[ "${1:-}" == "--log" || "${1:-}" == "--lesson" ]]; then
  fail "pass --log or --lesson, not both"
fi

# Pinned, the log and the Inbox all hold one item per line.
BODY="${*:-}"
BODY="${BODY//[$'\r\n']/ }"
[[ -n "${BODY//[[:space:]]/}" ]] || fail "missing note body"
BODY=$(printf '%s' "$BODY" | strip_private)
BODY="${BODY#"${BODY%%[![:space:]]*}"}"
[[ -n "$BODY" ]] || fail "nothing is left once the <private> regions are removed"

TODAY=$(date +%Y-%m-%d)
if [[ "$TARGET" == "lesson" ]]; then
  save_lesson "$BODY"
else
  save_note "$TARGET" "$BODY"
fi
exit 0
