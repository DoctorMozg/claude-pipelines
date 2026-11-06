#!/usr/bin/env bash
set -euo pipefail

# CLI helper invoked by the /lessons-promote skill. It lists lessons to promote, archives one once its
# rule is written, and records a declined one so the SessionStart hint skips it until it recurs.
#
# Usage: lessons-promote.sh list [<id>...]
#        lessons-promote.sh archive <id> <target>
#        lessons-promote.sh decline <id>

# Hooks get CLAUDE_PLUGIN_ROOT (PLUGIN_ROOT under Codex); a skill's Bash call gets neither, so set both.
PLUGIN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CLAUDE_PLUGIN_ROOT=$PLUGIN_ROOT
# shellcheck source=lib/common.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/lessons.sh"
# shellcheck source=lib/curator.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/curator.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
LESSONS_FILE="${MEMORY_DIR}/lessons.md"
ARCHIVE_FILE="${MEMORY_DIR}/lessons.archive.md"
OPS_LOG="${MEMORY_DIR}/lessons.ops.jsonl"
USAGE="usage: lessons-promote.sh list [<id>...] | archive <id> <target> | decline <id>"

fail() {
  echo "lessons-promote.sh: $1" >&2
  exit 2
}

check_id() {
  [[ "$1" =~ ^[LI]-[0-9]+$ ]] || fail "'$1' is not a lesson id such as L-0042 or I-0107"
}

# lesson_line <id> — the lesson's line in lessons.md; empty when it is not there.
lesson_line() {
  [[ -f "$LESSONS_FILE" ]] || return 0
  awk -v tag="[$1]" '$1 == "-" && $2 == tag { print; exit }' "$LESSONS_FILE"
}

# list [<id>...] — the named lessons in that order, or else the promotion candidates, most seen first.
cmd_list() {
  local ids=() lines=() id line
  if [[ $# -gt 0 ]]; then
    ids=("$@")
  else
    while IFS= read -r id; do
      [[ -n "$id" ]] && ids+=("$id")
    done < <(promotion_candidates "$LESSONS_FILE")
  fi
  # Every id is checked before anything is printed, so a typo never yields a partial list.
  for id in ${ids[@]+"${ids[@]}"}; do
    check_id "$id"
    line=$(lesson_line "$id")
    [[ -n "$line" ]] || fail "$id is not in ${LESSONS_FILE}"
    lines+=("$line")
  done
  if [[ ${#lines[@]} -gt 0 ]]; then printf '%s\n' "${lines[@]}"; fi
}

# archive <id> <target> — move the lesson to the archive as promoted to <target>.
cmd_archive() {
  local id="$1" target="$2" line
  check_id "$id"
  [[ "$target" =~ ^[^[:space:]]+\.md$ ]] || fail "target '$target' must be a .md path without spaces"
  {
    flock 9 2>/dev/null || true
    line=$(lesson_line "$id")
    [[ -n "$line" ]] || fail "$id is not in ${LESSONS_FILE}; the curator may have merged or archived it"
    # The archive line comes first: if the rewrite fails, the lesson is in both files, never in neither.
    printf '%s promoted_to=%s: %s\n' "$TODAY" "$target" "$line" >>"$ARCHIVE_FILE"
    awk -v tag="[$id]" '!($1 == "-" && $2 == tag)' "$LESSONS_FILE" | atomic_write "$LESSONS_FILE"
  } 9>>"${LESSONS_FILE}.lock"
  curator_event "$OPS_LOG" promoted "$id to $target"
  printf 'Archived %s as promoted to %s\n' "$id" "$target"
}

# decline <id> — skip the lesson in the candidates until its count grows past today's.
cmd_decline() {
  local id="$1" line n declined
  check_id "$id"
  declined=$(declined_file "$LESSONS_FILE")
  {
    flock 9 2>/dev/null || true
    line=$(lesson_line "$id")
    [[ -n "$line" ]] || fail "$id is not in ${LESSONS_FILE}"
    n=$(awk '{ for (i = 3; i <= NF && $i != "::"; i++) if ($i ~ /^n=[0-9]+$/) { print substr($i, 3); exit } }' <<<"$line")
    {
      awk -v id="$id" '$1 != id' "$declined" 2>/dev/null || true
      printf '%s %s\n' "$id" "${n:-0}"
    } | atomic_write "$declined"
  } 9>>"${LESSONS_FILE}.lock"
  curator_event "$OPS_LOG" declined "$id at n=${n:-0}"
  printf 'Declined %s at n=%s; it is offered again once it recurs\n' "$id" "${n:-0}"
}

TODAY=$(date +%Y-%m-%d)
case "${1:-}" in
  list)
    shift
    cmd_list "$@"
    ;;
  archive)
    [[ $# -eq 3 ]] || fail "$USAGE"
    cmd_archive "$2" "$3"
    ;;
  decline)
    [[ $# -eq 2 ]] || fail "$USAGE"
    cmd_decline "$2"
    ;;
  *) fail "$USAGE" ;;
esac
exit 0
