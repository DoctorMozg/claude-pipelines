#!/usr/bin/env bash
# set -eo (not -euo): CLAUDE_PLUGIN_ROOT may legitimately be unset outside the harness.
set -eo pipefail

# SessionStart hook (once: true) — injects the using-mozg-pipelines routing TABLE
# (the "## Techniques" section of the skill) so every new session knows which
# skill to invoke for a given task phrase. Injects the table only, never the
# whole SKILL.md: frontmatter, Overview, and Verification are authoring noise
# here, and an uncapped injection previously truncated mid-table.

SKILL_FILE="${CLAUDE_PLUGIN_ROOT:-}/skills/using-mozg-pipelines/SKILL.md"
MAX_LINES=200
MAX_CHARS=8000

command -v jq >/dev/null 2>&1 || exit 0
[[ -f "$SKILL_FILE" && -s "$SKILL_FILE" ]] || exit 0

content=$(awk '/^## Techniques/{f=1;next} /^## /{f=0} f' "$SKILL_FILE" | head -n "$MAX_LINES") || exit 0
[[ -n "$content" ]] || exit 0

if (( ${#content} > MAX_CHARS )); then
  content="${content:0:$MAX_CHARS}
...[truncated]"
fi

printf '%s' "$content" | jq -Rs \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ("Mozg pipelines routing map (using-mozg-pipelines):\n" + .)}}' || exit 0

exit 0
