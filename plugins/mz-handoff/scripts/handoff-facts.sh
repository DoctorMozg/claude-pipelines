#!/usr/bin/env bash
set -euo pipefail

# Prints the facts a handoff is built from: session ids, git state, the files this session wrote,
# running tasks and the user's own messages, verbatim. Used by the handoff skill.
# Usage: handoff-facts.sh [--since <ISO time>] [<transcript.jsonl>]

# Hooks get CLAUDE_PLUGIN_ROOT (PLUGIN_ROOT under Codex); a skill's Bash call gets neither, so set both.
PLUGIN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CLAUDE_PLUGIN_ROOT=$PLUGIN_ROOT
# shellcheck source=lib/handoff.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/handoff.sh"

MAX_MESSAGES=40
MAX_MESSAGE_CHARS=600
MAX_FILES=40
MAX_STATUS_LINES=30
MAX_COMMITS=20

die() {
  echo "handoff-facts.sh: $1" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || die "jq is required"

SINCE=""
TRANSCRIPT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)
      [[ $# -ge 2 ]] || die "--since needs an ISO time such as 2026-11-05T18:30:00Z"
      SINCE="$2"
      shift 2
      ;;
    -*) die "unknown option $1" ;;
    *)
      TRANSCRIPT="$1"
      shift
      ;;
  esac
done

# A transcript named on the command line must exist; one looked up by session id may not be found
# (an eval run keeps it out of reach), and then the git facts still come out without it.
MISSING=""
if [[ -n "$TRANSCRIPT" ]]; then
  [[ -f "$TRANSCRIPT" ]] || die "transcript ${TRANSCRIPT} not found"
  SESSION_ID=$(basename "$TRANSCRIPT" .jsonl)
else
  [[ -n "${CLAUDE_CODE_SESSION_ID:-}" ]] || die "no transcript given and CLAUDE_CODE_SESSION_ID is unset"
  SESSION_ID="$CLAUDE_CODE_SESSION_ID"
  TRANSCRIPT=$(find "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects" -maxdepth 2 -name "${SESSION_ID}.jsonl" 2>/dev/null | head -n 1 || true)
  if [[ -z "$TRANSCRIPT" ]]; then
    MISSING="no transcript found for session ${SESSION_ID}; take the user's words and the files from the conversation"
    echo "handoff-facts.sh: ${MISSING}" >&2
  fi
fi

ROOT=$(find_project_root)
HANDOFF_DIR="${ROOT}/.mz/handoff"
STARTED=""
if [[ -n "$TRANSCRIPT" ]]; then
  # Transcripts can hold a truncated line, so every jq pass skips lines that don't parse.
  STARTED=$(jq -rR 'fromjson? | .timestamp // empty' "$TRANSCRIPT" 2>/dev/null | head -n 1 || true)
fi

HANDOFF=$(handoff_for_session "$HANDOFF_DIR" "$SESSION_ID")
[[ -n "$HANDOFF" ]] || HANDOFF="${HANDOFF_DIR}/$(date +%Y_%m_%d_%H%M)_${SESSION_ID:0:8}.md"

user_messages() {
  jq -rR --arg since "$SINCE" --argjson max "$MAX_MESSAGE_CHARS" '
    fromjson?
    | select(.type == "user" and .isMeta != true and .isCompactSummary != true)
    | select((.timestamp // "") > $since)
    | (.message.content
        | if type == "string" then .
          elif type == "array" and all(.[]; .type != "tool_result") then map(select(.type == "text") | .text) | join(" ")
          else empty end) as $text
    | select($text != "")
    | select([ "<task-notification>", "<local-command-", "Another Claude session sent", "[Cross-session" ]
             | any(. as $p | $text | startswith($p)) | not)
    | ($text
        | if startswith("<command-name>") then
            ([(capture("<command-name>(?<c>[^<]*)</command-name>") | .c)?, (capture("<command-args>(?<a>[^<]*)</command-args>") | .a)?]
             | map(select(. != null and . != "")) | join(" "))
          else . end
        | sub("^\\s+"; "") | sub("\\s+$"; "") | gsub("\\s*\\n\\s*"; " / ")) as $line
    | "- [\(.timestamp[0:16])] \(if ($line | length) > $max then $line[0:$max] + " …" else $line end)"
  ' "$TRANSCRIPT" 2>/dev/null | tail -n "$MAX_MESSAGES" || true
}

files_written() {
  jq -rR --arg since "$SINCE" '
    fromjson?
    | select(.type == "assistant" and (.timestamp // "") > $since)
    | .message.content[]?
    | select(.type == "tool_use" and (.name == "Edit" or .name == "Write" or .name == "NotebookEdit"))
    | .input.file_path // .input.notebook_path // empty
  ' "$TRANSCRIPT" 2>/dev/null | awk '!seen[$0]++' | tail -n "$MAX_FILES" | sed "s|^${ROOT}/||" || true
}

running_tasks() {
  local file status
  while IFS= read -r file; do
    [[ "$file" == .mz/task/*/state.md && -f "${ROOT}/${file}" ]] || continue
    status=$(grep -m 1 '^Status:' "${ROOT}/${file}" || true)
    [[ "$status" == *complete* ]] && continue
    printf -- '- %s  %s  %s\n' "${file%state.md}" "$status" "$(grep -m 1 '^Phase:' "${ROOT}/${file}" || true)"
  done <<<"$1"
}

git_facts() {
  if ! git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    printf 'branch: none\nhead: none\n'
    return 0
  fi
  printf 'branch: %s\nhead: %s\n' "$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo none)" \
    "$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo none)"
}

FILES=""
[[ -z "$TRANSCRIPT" ]] || FILES=$(files_written)

printf 'handoff_file: %s\n' "${HANDOFF#"$ROOT"/}"
printf 'session_id: %s\nclaude_pid: %s\ntranscript: %s\nwritten_at: %s\ncompactions: %s\ncwd: %s\n' \
  "$SESSION_ID" "$(claude_pid)" "${TRANSCRIPT:-none}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "$(if [[ -n "$TRANSCRIPT" ]]; then compaction_count "$TRANSCRIPT"; else echo unknown; fi)" "$ROOT"
git_facts
printf 'session_started: %s\n' "${STARTED:-unknown}"

printf '\n## Running tasks (state.md files this session wrote)\n%s\n' "$(running_tasks "$FILES")"
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  printf '\n## Git status\n%s\n' "$(git -C "$ROOT" status --short 2>/dev/null | head -n "$MAX_STATUS_LINES" || true)"
  if [[ -n "$STARTED" ]]; then
    printf '\n## Commits since the session started\n%s\n' \
      "$(git -C "$ROOT" log --since="$STARTED" --oneline -n "$MAX_COMMITS" 2>/dev/null || true)"
  fi
fi
if [[ -n "$MISSING" ]]; then
  printf '\n## Transcript facts unavailable\n%s\n' "$MISSING"
  exit 0
fi
printf '\n## Files written this session\n%s\n' "$FILES"
printf '\n## User messages (verbatim, oldest first, last %s)\n%s\n' "$MAX_MESSAGES" "$(user_messages)"
