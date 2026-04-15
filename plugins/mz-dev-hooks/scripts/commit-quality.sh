#!/usr/bin/env bash
set -euo pipefail

# PreToolUse(Bash) with if: "Bash(git commit*)" — warns on non-conventional commits.
# Never blocks (always exit 0), only adds additionalContext.

INPUT=$(cat)

CMD=$(jq -r '.tool_input.command // empty' <<< "$INPUT" 2>/dev/null || echo "")

if [[ -z "$CMD" ]]; then
  exit 0
fi

# Only validate commits with -m flag (skip interactive commits, amends without message)
if ! echo "$CMD" | grep -qP '\s-m\s'; then
  exit 0
fi

# Extract the commit message — handles both single and double quotes
MSG=$(echo "$CMD" | grep -oP -- '-m\s+["'\'']\K[^"'\'']+' | head -1)

if [[ -z "$MSG" ]]; then
  # Try heredoc-style: -m "$(cat <<'EOF'
  MSG=$(echo "$CMD" | grep -oP -- '-m\s+["'\'']\$\(cat\s+<<.*?EOF[^)]*\)' | head -1)
  if [[ -n "$MSG" ]]; then
    # Can't reliably parse heredoc, skip validation
    exit 0
  fi
  exit 0
fi

WARNINGS=""

# Check conventional commit format
if ! echo "$MSG" | grep -qP '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:\s.+'; then
  WARNINGS="Commit message doesn't follow conventional commits format (type(scope): description). "
fi

# Check subject line length (first line)
FIRST_LINE=$(echo "$MSG" | head -1)
if [[ ${#FIRST_LINE} -gt 72 ]]; then
  WARNINGS="${WARNINGS}Subject line is ${#FIRST_LINE} chars (limit: 72). "
fi

# Check for empty description after prefix
if echo "$MSG" | grep -qP '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:\s*$'; then
  WARNINGS="${WARNINGS}Commit message has a type prefix but no description. "
fi

if [[ -n "$WARNINGS" ]]; then
  jq -n --arg msg "Commit quality: ${WARNINGS}Expected format: type(scope): description (e.g., feat(auth): add OAuth2 flow)" \
    '{hookSpecificOutput: {additionalContext: $msg}}'
fi

exit 0
