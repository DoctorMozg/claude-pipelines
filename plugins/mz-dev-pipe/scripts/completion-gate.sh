#!/usr/bin/env bash
set -euo pipefail

# Stop hook — blocks session stop when a pipeline task is actively in progress.
# Prevents accidental termination mid-pipeline.
# Exit 2 = block stop, exit 0 = allow stop.

# Guard against infinite loops: if this hook already triggered a stop-block,
# the user's next explicit stop should be allowed through.
GATE_FLAG="${CLAUDE_PROJECT_DIR:-.}/.mz/.completion_gate_active"

if [[ -f "$GATE_FLAG" ]]; then
  rm -f "$GATE_FLAG"
  exit 0
fi

TASK_DIR="${CLAUDE_PROJECT_DIR:-.}/.mz/task"

if [[ ! -d "$TASK_DIR" ]]; then
  exit 0
fi

# Find any active pipeline tasks (status: in_progress, not in a terminal phase)
ACTIVE_TASKS=""
for state_file in "$TASK_DIR"/*/state.md; do
  [[ -f "$state_file" ]] || continue

  STATUS=$(grep -oP 'Status:\s*\K\S+' "$state_file" 2>/dev/null || echo "")
  PHASE=$(grep -oP 'Phase:\s*\K\S+' "$state_file" 2>/dev/null || echo "")
  TASK_NAME=$(basename "$(dirname "$state_file")")

  # Skip completed, aborted, or failed tasks
  if [[ "$STATUS" == "completed" ]] || \
     [[ "$STATUS" == "aborted"* ]] || \
     [[ "$STATUS" == "failed" ]]; then
    continue
  fi

  # Skip tasks in terminal phases
  if [[ "$PHASE" == "completed" ]] || \
     [[ "$PHASE" == "aborted"* ]] || \
     [[ "$PHASE" == "consensus_reached" ]]; then
    continue
  fi

  if [[ "$STATUS" == "in_progress" ]] || [[ "$STATUS" == "started" ]]; then
    ACTIVE_TASKS="${ACTIVE_TASKS}${TASK_NAME} (phase: ${PHASE}), "
  fi
done

if [[ -n "$ACTIVE_TASKS" ]]; then
  ACTIVE_TASKS="${ACTIVE_TASKS%, }"

  # Set the gate flag so the user's next stop attempt goes through
  mkdir -p "$(dirname "$GATE_FLAG")"
  touch "$GATE_FLAG"

  echo "{\"hookSpecificOutput\":{\"decision\":\"block\",\"reason\":\"Pipeline task still active: ${ACTIVE_TASKS}. Complete or abort the task first. Stop again to force quit.\"}}"
  exit 2
fi

exit 0
