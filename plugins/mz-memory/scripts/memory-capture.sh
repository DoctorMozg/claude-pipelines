#!/usr/bin/env bash
set -euo pipefail

# SessionEnd hook — captures completed task summaries into project memory.
# Targets <1.5s; offloads optional LLM compression to a detached child.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
TASK_DIR="${PROJECT_DIR}/.mz/task"
AGENT_MEMORY_DIR="${PROJECT_DIR}/.claude/agent-memory"

MAX_LOG_LINES=200
COMPRESS_THRESHOLD=300

[[ -d "$TASK_DIR" ]] || exit 0

ensure_memory_file "$MEMORY_FILE"

TODAY=$(date +%Y-%m-%d)
GIT_BRANCH=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
GIT_SHA=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || true)

NEW_BLOCK=""

for state_file in "$TASK_DIR"/*/state.md; do
  [[ -f "$state_file" ]] || continue

  STATUS=$(grep -o 'Status[*]*: [a-z_]*' "$state_file" 2>/dev/null | head -1 | sed 's/.*: //')
  [[ "$STATUS" == "completed" ]] || continue

  TASK_NAME=$(basename "$(dirname "$state_file")")

  # Dedup by (date, task) so a re-run on a later day produces a fresh entry.
  if grep -qF "[${TODAY}] ${TASK_NAME}" "$MEMORY_FILE" 2>/dev/null; then
    continue
  fi

  PHASE=$(grep -o 'Phase[*]*: [a-z_]*' "$state_file" 2>/dev/null | head -1 | sed 's/.*: //')

  ENTRY="- [${TODAY}] ${TASK_NAME}"
  [[ -n "$PHASE" ]] && ENTRY="${ENTRY} (phase=${PHASE})"
  if [[ -n "$GIT_BRANCH" && -n "$GIT_SHA" ]]; then
    ENTRY="${ENTRY} [${GIT_BRANCH}@${GIT_SHA}]"
  fi

  # Pull a "## Decisions" / "## Lessons" / "## Notes" section out of state.md
  # if present. Cap at 10 lines to keep the log compact.
  EXTRA=$(awk '
    /^##[[:space:]]+(Decisions|Lessons|Notes)[[:space:]]*$/ { capture = 1; next }
    /^##[[:space:]]/ && capture { capture = 0 }
    capture && NF { print "  " $0 }
  ' "$state_file" 2>/dev/null | head -10)

  NEW_BLOCK="${NEW_BLOCK}${ENTRY}"$'\n'
  [[ -n "$EXTRA" ]] && NEW_BLOCK="${NEW_BLOCK}${EXTRA}"$'\n'

  # Per-agent bridge: if the state file mentions [agent-name] for any agent
  # under .claude/agent-memory, copy the entry into that agent's MEMORY.md.
  if [[ -d "$AGENT_MEMORY_DIR" ]]; then
    for agent_dir in "$AGENT_MEMORY_DIR"/*/; do
      [[ -d "$agent_dir" ]] || continue
      AGENT_NAME=$(basename "$agent_dir")
      if grep -qiF "[${AGENT_NAME}]" "$state_file" 2>/dev/null; then
        AGENT_FILE="${agent_dir}MEMORY.md"
        [[ -f "$AGENT_FILE" ]] || printf '# %s memory\n\n' "$AGENT_NAME" > "$AGENT_FILE"
        printf '%s\n' "$ENTRY" >> "$AGENT_FILE"
      fi
    done
  fi
done

# Strip <private>...</private> regions before persisting.
NEW_BLOCK=$(printf '%s' "$NEW_BLOCK" | strip_private)

if [[ -n "$NEW_BLOCK" ]]; then
  printf '%s' "$NEW_BLOCK" | prepend_to_log "$MEMORY_FILE" "$MAX_LOG_LINES"
fi

# Optional background compression. Off by default — opt in with
# MZ_MEMORY_COMPRESS=1. Detached so we never block SessionEnd past its budget.
if [[ "${MZ_MEMORY_COMPRESS:-0}" == "1" ]] && command -v claude >/dev/null 2>&1; then
  LOG_LEN=$(extract_log "$MEMORY_FILE" 9999 | grep -cE '^- ' || true)
  if [[ "${LOG_LEN:-0}" -gt "$COMPRESS_THRESHOLD" ]]; then
    nohup "${SCRIPT_DIR}/memory-compress.sh" >/dev/null 2>&1 &
    disown 2>/dev/null || true
  fi
fi

exit 0
