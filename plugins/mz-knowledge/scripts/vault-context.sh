#!/usr/bin/env bash
# Injects Obsidian vault context at session start.
# Reads vault path from OBSIDIAN_VAULT_PATH or MZ_VAULT_PATH env vars.
# Outputs JSON with additionalContext for SessionStart hook event.

VAULT="${OBSIDIAN_VAULT_PATH:-${MZ_VAULT_PATH:-}}"

if [[ -z "$VAULT" || ! -d "$VAULT" ]]; then
  echo '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":""}}'
  exit 0
fi

TODAY=$(date +%Y-%m-%d)
CONTEXT=""

# Today's daily note
DAILY_NOTE="$VAULT/daily/$TODAY.md"
if [[ -f "$DAILY_NOTE" ]]; then
  CONTEXT="Today's daily note: $TODAY.md"
fi

# MOC list (00 - MOCs/ directory)
MOC_DIR="$VAULT/00 - MOCs"
if [[ -d "$MOC_DIR" ]]; then
  MOC_LIST=$(find "$MOC_DIR" -maxdepth 1 -name "*.md" -not -name ".*" -print0 2>/dev/null | \
    xargs -0 -I{} basename {} .md 2>/dev/null | head -20 | tr '\n' ', ' | sed 's/,$//')
  if [[ -n "$MOC_LIST" ]]; then
    CONTEXT="${CONTEXT}\nVault MOCs: ${MOC_LIST}"
  fi
fi

# Last 3 modified notes (excluding attachments/system files)
RECENT=$(find "$VAULT" -maxdepth 3 -name "*.md" -not -path "*/.obsidian/*" \
  -not -name ".*" -print0 2>/dev/null | \
  xargs -0 ls -t 2>/dev/null | head -3 | xargs -I{} basename {} .md 2>/dev/null | \
  tr '\n' ', ' | sed 's/,$//')
if [[ -n "$RECENT" ]]; then
  CONTEXT="${CONTEXT}\nRecently modified: ${RECENT}"
fi

# Build JSON — escape the context string
CONTEXT_ESCAPED=$(printf '%s' "$CONTEXT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')

printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":%s}}\n' "$CONTEXT_ESCAPED"
