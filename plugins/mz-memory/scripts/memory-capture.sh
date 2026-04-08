#!/usr/bin/env bash
set -euo pipefail

# SessionEnd hook — captures completed tasks into .mz/memory/MEMORY.md.
# Must complete within 1.5s. Shell-only operations, no external tools.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MEMORY_DIR="${PROJECT_DIR}/.mz/memory"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
TASK_DIR="${PROJECT_DIR}/.mz/task"

MAX_LINES=200

if [[ ! -d "$TASK_DIR" ]]; then
  exit 0
fi

mkdir -p "$MEMORY_DIR"

# Seed memory file if it doesn't exist
if [[ ! -f "$MEMORY_FILE" ]]; then
  cat > "$MEMORY_FILE" <<'SEED'
# Project Memory

<!-- Entries below are auto-managed by mz-memory. Most recent first. -->
SEED
fi

# Collect new completed task entries
NEW_ENTRIES=""
TODAY=$(date +%Y-%m-%d)

for state_file in "$TASK_DIR"/*/state.md; do
  [[ -f "$state_file" ]] || continue

  # Extract status — handles both plain "Status:" and markdown "**Status**:"
  STATUS=$(grep -o 'Status[*]*: [a-z_]*' "$state_file" 2>/dev/null | head -1 | sed 's/.*: //')

  if [[ "$STATUS" != "completed" ]]; then
    continue
  fi

  TASK_NAME=$(basename "$(dirname "$state_file")")

  # Deduplicate: skip if already in memory
  if grep -qF "$TASK_NAME" "$MEMORY_FILE" 2>/dev/null; then
    continue
  fi

  # Extract phase for context
  PHASE=$(grep -o 'Phase[*]*: [a-z_]*' "$state_file" 2>/dev/null | head -1 | sed 's/.*: //')

  NEW_ENTRIES="${NEW_ENTRIES}- [${TODAY}] Completed: ${TASK_NAME}"
  if [[ -n "$PHASE" ]]; then
    NEW_ENTRIES="${NEW_ENTRIES} (phase: ${PHASE})"
  fi
  NEW_ENTRIES="${NEW_ENTRIES}
"
done

# Nothing new to add
if [[ -z "$NEW_ENTRIES" ]]; then
  exit 0
fi

# Prepend new entries after the header (first 3 lines are header + comment)
TMPFILE=$(mktemp)
head -n 3 "$MEMORY_FILE" > "$TMPFILE"
printf '%s' "$NEW_ENTRIES" >> "$TMPFILE"
tail -n +4 "$MEMORY_FILE" >> "$TMPFILE"

# Prune to MAX_LINES
head -n "$MAX_LINES" "$TMPFILE" > "$MEMORY_FILE"
rm -f "$TMPFILE"

exit 0
