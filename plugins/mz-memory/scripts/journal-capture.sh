#!/usr/bin/env bash
set -euo pipefail

# PostToolUse(AskUserQuestion) — records every approval gate and input prompt
# to the global interaction journal (.mz/journal.md). This is the deterministic
# "audit guarantee" layer: it fires even when the model has forgotten it is
# mid-gate. Logging only — emits no hook output, always exits 0.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

INPUT=$(cat)

# Only AskUserQuestion is journaled; the matcher should guarantee this, but a
# defensive re-check keeps the script safe if invoked directly or mis-wired.
TOOL=$(jq -r '.tool_name // empty' <<<"$INPUT" 2>/dev/null || echo "")
[[ "$TOOL" == "AskUserQuestion" ]] || exit 0

PROJECT_DIR=$(find_project_root)
JOURNAL_FILE="${PROJECT_DIR}/.mz/journal.md"

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SESSION=$(jq -r '.session_id // "unknown"' <<<"$INPUT" 2>/dev/null || echo "unknown")

# Verbatim capture. The exact shape of tool_input / tool_response can vary, so
# dump them as compact JSON rather than assuming a schema.
QUESTIONS=$(jq -c '.tool_input.questions // .tool_input // {}' <<<"$INPUT" 2>/dev/null || echo "{}")
RESPONSE=$(jq -c '.tool_response // {}' <<<"$INPUT" 2>/dev/null || echo "{}")

BLOCK=$(printf '### %s · session %s · AskUserQuestion\n\nquestions (verbatim):\n%s\n\nresponse (verbatim):\n%s' \
  "$TS" "$SESSION" "$QUESTIONS" "$RESPONSE")

printf '%s' "$BLOCK" | journal_append "$JOURNAL_FILE" 2>/dev/null || exit 0

exit 0
