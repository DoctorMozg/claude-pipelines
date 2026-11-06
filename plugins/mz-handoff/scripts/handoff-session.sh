#!/usr/bin/env bash
set -euo pipefail

# SessionStart (startup|clear|compact): flags a compaction for handoff-stop.sh, loads this
# terminal's handoff after /clear, and lists open handoffs on startup. Advisory: exits 0.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/handoff.sh
source "${SCRIPT_DIR}/lib/handoff.sh"
command -v jq >/dev/null 2>&1 || exit 0

# A /clear picks up a handoff from the last day; the startup list shows the last three days.
CLEAR_MAX_AGE_MIN=1440
LIST_MAX_AGE_MIN=4320
LIST_MAX=3
MAX_CHARS=2000

INPUT=$(cat)
field() { jq -r --arg key "$1" '.[$key] // empty | tostring' <<<"$INPUT" 2>/dev/null || echo ""; }

SOURCE=$(field source)
SESSION_ID=$(field session_id)
[[ "$SESSION_ID" =~ ^[A-Za-z0-9_-]+$ ]] || exit 0

ROOT=$(find_project_root)
HANDOFF_DIR="${ROOT}/.mz/handoff"

emit_context() {
  local text="$1"
  if [[ ${#text} -gt $MAX_CHARS ]]; then
    text="${text:0:$MAX_CHARS}
...[handoff truncated]"
  fi
  jq -n --arg ctx "$text" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
}

relative() { printf '%s\n' "${1#"$ROOT"/}"; }

open_handoffs() {
  local file
  while IFS= read -r file; do
    [[ "$(handoff_field "$file" status)" == "open" ]] && printf '%s\n' "$file"
  done < <(handoff_files "$HANDOFF_DIR" "$1")
  return 0
}

load_handoff() {
  local file="$1" next
  next=$(awk '$0 == "## Next" { inside = 1; next } inside && /^## / { exit } inside && NF { print }' "$file" | head -n 5 || true)
  emit_context "The previous session in this terminal wrote a handoff before /clear: $(relative "$file") (written $(handoff_field "$file" written_at), after $(handoff_field "$file" compactions) compactions, at commit $(handoff_field "$file" head)). Its old transcript is $(handoff_field "$file" transcript).
Goal: $(handoff_section_head "$file" Goal)
Next:
${next}
The resume mode of the /mz-handoff:handoff skill loads the whole file, checks it against git and runs its verify commands."
}

list_handoffs() {
  local file lines=""
  while IFS= read -r file; do
    lines+="- $(relative "$file") (branch $(handoff_field "$file" branch), written $(handoff_field "$file" written_at)): $(handoff_section_head "$file" Goal)
"
  done < <(open_handoffs "$LIST_MAX_AGE_MIN" | head -n "$LIST_MAX" || true)
  [[ -n "$lines" ]] || return 0
  emit_context "Open handoffs from earlier sessions in this project, newest first. The resume mode of the /mz-handoff:handoff skill loads one when the user picks it:
${lines}"
}

case "$SOURCE" in
  compact)
    # MZ_HANDOFF_AFTER=0 turns off only the automatic nudge; written handoffs still load.
    [[ "$(handoff_threshold)" -gt 0 ]] || exit 0
    if ! mkdir -p "${HANDOFF_DIR}/.due" || ! : >"${HANDOFF_DIR}/.due/${SESSION_ID}"; then
      echo "mz-handoff: can't flag the compaction under ${HANDOFF_DIR}/.due" >&2
    fi
    ;;
  clear)
    PID=$(claude_pid)
    MATCH=""
    if [[ -n "$PID" ]]; then
      while IFS= read -r file; do
        if [[ "$(handoff_field "$file" claude_pid)" == "$PID" ]]; then
          MATCH="$file"
          break
        fi
      done < <(open_handoffs "$CLEAR_MAX_AGE_MIN")
    else
      echo "mz-handoff: no claude ancestor process found, listing open handoffs instead" >&2
    fi
    if [[ -n "$MATCH" ]]; then load_handoff "$MATCH"; else list_handoffs; fi
    ;;
  startup)
    find "${HANDOFF_DIR}/.due" "${HANDOFF_DIR}/.nudged" -type f -mtime +7 -delete 2>/dev/null || true
    list_handoffs
    ;;
esac
exit 0
