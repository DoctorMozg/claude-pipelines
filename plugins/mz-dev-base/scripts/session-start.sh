#!/usr/bin/env bash
set -eo pipefail

# SessionStart hook (once: true) — injects using-mozg-pipelines routing map
# so every new session knows which skill to invoke for a given task phrase.

SKILL_FILE="${CLAUDE_PLUGIN_ROOT}/skills/using-mozg-pipelines/SKILL.md"
MAX_CHARS=8000

if [[ ! -f "$SKILL_FILE" ]] || [[ ! -s "$SKILL_FILE" ]]; then
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":""}}\n'
  exit 0
fi

content=$(head -c "$MAX_CHARS" "$SKILL_FILE")

printf '%s' "$content" | jq -Rs \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ("Mozg pipelines routing map (using-mozg-pipelines):\n" + .)}}'

exit 0
