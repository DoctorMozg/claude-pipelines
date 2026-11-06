#!/usr/bin/env bash
set -euo pipefail

# SessionEnd hook — logs completed tasks into project memory and collects every task's
# ## Lessons into the lessons Inbox. Targets <1.5s; offloads LLM compression to a detached child.

# shellcheck source=lib/common.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"
# shellcheck source=lib/lessons.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/lessons.sh"
# shellcheck source=lib/curator.sh
source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/curator.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
LESSONS_FILE="${MEMORY_DIR}/lessons.md"
TASK_DIR="${PROJECT_DIR}/.mz/task"
AGENT_MEMORY_DIR="${PROJECT_DIR}/.claude/agent-memory"

# Parsing a long task history would exceed the 1.5 s SessionEnd budget, and a killed run never advances the marker.
MAX_FIRST_RUN_TASKS=50
# Decisions and Notes lines copied under each log entry, and lesson bullets taken per task.
EXTRA_LINES=10
LESSONS_PER_TASK=10

[[ -d "$TASK_DIR" ]] || exit 0

# An intact MEMORY.md needs no write, so the dir check catches a read-only dir the helper lets through.
# The marker stays put, so the skipped tasks are captured once the dir is writable again.
if ! ensure_memory_file "$MEMORY_FILE" || [[ ! -w "$MEMORY_DIR" ]]; then
  echo "memory-capture.sh: can't write ${MEMORY_DIR}, skipping capture" >&2
  exit 0
fi

TODAY=$(date +%Y-%m-%d)
GIT_BRANCH=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
GIT_SHA=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || true)

# The marker's mtime is the previous capture time. Only state files changed since
# then are parsed, so a finished task is logged once per completion.
CAPTURE_MARKER="${MEMORY_DIR}/.last-capture"
NEXT_MARKER="${CAPTURE_MARKER}.next"
touch "$NEXT_MARKER"

FIRST_RUN=0
if [[ -f "$CAPTURE_MARKER" ]]; then
  CHANGED=$(find "$TASK_DIR" -mindepth 2 -maxdepth 2 -name state.md -newer "$CAPTURE_MARKER" 2>/dev/null | sort || true)
else
  FIRST_RUN=1
  # ls -t is the portable mtime sort (find -printf is GNU-only); task dir names are skill-generated.
  # shellcheck disable=SC2012
  CHANGED=$(ls -t "$TASK_DIR"/*/state.md 2>/dev/null | head -n "$MAX_FIRST_RUN_TASKS" | sort || true)
fi

# scan_state_files <out_dir> <state_file>... — read every changed state file in one awk pass and
# write <out_dir>/log (entries and their Decisions lines), /lessons (records) and /agents (bridge lines).
# A few processes per task cost about 9 ms each, which pushed a 50-task backlog past the budget.
scan_state_files() {
  local out_dir="$1"
  shift
  MZ_MEMORY_FILE="$MEMORY_FILE" MZ_AGENTS="$AGENTS" awk -v out="$out_dir" -v first_run="$FIRST_RUN" \
    -v today="$TODAY" -v branch="$GIT_BRANCH" -v sha="$GIT_SHA" -v fs="$MZ_LESSON_FS" \
    -v max_lessons="$LESSONS_PER_TASK" -v max_extra="$EXTRA_LINES" -f "${CLAUDE_PLUGIN_ROOT}/scripts/awk/scan-state-files.awk" "$@"
}

# An unreadable file is skipped here: mawk stops at one, which would fail the capture every session.
STATE_FILES=()
while IFS= read -r state_file; do
  if [[ -n "$state_file" && -f "$state_file" && -r "$state_file" ]]; then STATE_FILES+=("$state_file"); fi
done <<<"$CHANGED"

AGENTS=""
if [[ -d "$AGENT_MEMORY_DIR" ]]; then
  for agent_dir in "$AGENT_MEMORY_DIR"/*/; do
    [[ -d "$agent_dir" ]] || continue
    agent_dir="${agent_dir%/}"
    AGENTS+="${agent_dir##*/}"$'\n'
  done
fi

SCAN_DIR=$(mktemp -d)
trap 'rm -rf -- "$SCAN_DIR"' EXIT
if [[ ${#STATE_FILES[@]} -gt 0 ]]; then
  scan_state_files "$SCAN_DIR" "${STATE_FILES[@]}"
fi

if [[ -s "${SCAN_DIR}/agents" ]]; then
  while IFS=$'\t' read -r agent entry; do
    agent_file="${AGENT_MEMORY_DIR}/${agent}/MEMORY.md"
    [[ -f "$agent_file" ]] || printf '# %s memory\n\n' "$agent" >"$agent_file"
    printf '%s\n' "$entry" >>"$agent_file"
  done <"${SCAN_DIR}/agents"
fi

# Lessons are written before the log: a retry after a failed log write skips lessons already seen.
if [[ -s "${SCAN_DIR}/lessons" ]]; then
  strip_private <"${SCAN_DIR}/lessons" | add_lessons_to_inbox "$LESSONS_FILE" "$TODAY" "$GIT_SHA" >/dev/null
fi

# Strip <private>...</private> regions before persisting.
NEW_BLOCK=""
if [[ -s "${SCAN_DIR}/log" ]]; then
  NEW_BLOCK=$(strip_private <"${SCAN_DIR}/log")
fi

if [[ -n "$NEW_BLOCK" ]]; then
  printf '%s' "$NEW_BLOCK" | prepend_to_log "$MEMORY_FILE" "$MZ_LOG_MAX_LINES"
fi

# Advance only after the log write succeeded, so a failed run is retried next time.
mv -f "$NEXT_MARKER" "$CAPTURE_MARKER"

# The lessons cap holds without the LLM; eviction is a few hundred lines of awk, so it runs inline.
enforce_lessons_cap "$LESSONS_FILE" "$TODAY"

# Compression and curation are on by default and MZ_MEMORY_COMPRESS=0 opts out of both.
# Both run detached so SessionEnd never waits on the LLM.
if [[ "${MZ_MEMORY_COMPRESS:-1}" != "0" ]] && command -v claude >/dev/null 2>&1; then
  LOG_LEN=$(extract_log "$MEMORY_FILE" 9999 | awk -f "${CLAUDE_PLUGIN_ROOT}/scripts/awk/count-lines.awk")
  if [[ "${LOG_LEN:-0}" -gt "$MZ_COMPRESS_THRESHOLD" ]]; then
    nohup "${CLAUDE_PLUGIN_ROOT}/scripts/memory-compress.sh" >/dev/null 2>&1 &
    disown 2>/dev/null || true
  fi
fi
if curator_enabled && lessons_need_curation "$LESSONS_FILE"; then
  nohup "${CLAUDE_PLUGIN_ROOT}/scripts/lessons-curate.sh" >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi

exit 0
