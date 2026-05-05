#!/usr/bin/env bash
set -euo pipefail

# PreCompact hook — captures a handover summary BEFORE the harness compresses
# the transcript. Output goes to plain stdout (PreCompact rejects the
# hookSpecificOutput envelope) and is appended to the compaction prompt.
#
# Strategy:
#   1. Read the transcript_path from stdin JSON.
#   2. Tail the last N lines for an "in-flight state" anchor.
#   3. If MZ_MEMORY_PRECOMPACT_LLM=1 and `claude` is available, ask a fresh
#      Claude instance to produce a compact handover. Otherwise fall back to
#      a deterministic transcript tail.
#   4. Always include the existing pinned section so invariants survive.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
MEMORY_FILE="${PROJECT_DIR}/.mz/memory/MEMORY.md"

TAIL_LINES=200
LLM_TIMEOUT=20

# Read stdin without blocking forever: PreCompact always provides JSON.
INPUT=""
if [[ ! -t 0 ]]; then
  INPUT=$(cat || true)
fi

TRANSCRIPT_PATH=""
if [[ -n "$INPUT" ]] && command -v jq >/dev/null 2>&1; then
  TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
fi

PINNED=""
if [[ -f "$MEMORY_FILE" ]]; then
  PINNED=$(extract_pinned "$MEMORY_FILE" | sed '/^[[:space:]]*$/d')
fi

HANDOVER=""

if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  TAIL=$(tail -n "$TAIL_LINES" "$TRANSCRIPT_PATH" 2>/dev/null || true)

  if [[ -n "$TAIL" \
        && "${MZ_MEMORY_PRECOMPACT_LLM:-0}" == "1" \
        && -x "$(command -v claude || true)" ]]; then
    PROMPT='Summarize the in-flight working state from this Claude Code transcript tail. Output 8-15 bullet lines covering: current goal, last completed step, immediate next step, any unresolved blockers, key file paths or identifiers being worked on. Plain markdown, no preamble.'
    HANDOVER=$(printf '%s\n\n---\n\n%s' "$PROMPT" "$TAIL" \
      | timeout "$LLM_TIMEOUT" claude -p --output-format text 2>/dev/null || true)
  fi

  if [[ -z "$HANDOVER" ]]; then
    HANDOVER="Transcript tail (last ${TAIL_LINES} lines, deterministic fallback):
\`\`\`
${TAIL}
\`\`\`"
  fi
fi

{
  printf '[PreCompact] Handover snapshot from mz-memory:\n\n'
  if [[ -n "$PINNED" ]]; then
    printf '## Pinned (project invariants)\n%s\n\n' "$PINNED"
  fi
  if [[ -n "$HANDOVER" ]]; then
    printf '## In-flight state\n%s\n' "$HANDOVER"
  else
    printf '## In-flight state\n(no transcript available; rely on PostCompact reinject)\n'
  fi
} || true

exit 0
