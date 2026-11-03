#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook (startup, clear, compact): injects today's daily note, the MOC list and recent notes.
# The vault comes from OBSIDIAN_VAULT_PATH, then MZ_VAULT_PATH; with no vault, notes or jq it prints nothing.

MAX_MOCS=20
MAX_RECENT=3
MAX_CHARS=8000

VAULT="${OBSIDIAN_VAULT_PATH:-${MZ_VAULT_PATH:-}}"
[[ -n "$VAULT" && -d "$VAULT" ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

# Reads note paths, one per line, and prints their names without directory or .md, joined by ", ".
join_note_names() {
  local path name joined=""
  while IFS= read -r path; do
    name="${path##*/}"
    joined="${joined:+$joined, }${name%.md}"
  done
  printf '%s' "$joined"
}

lines=()

today=$(date +%Y-%m-%d)
if [[ -f "$VAULT/daily/$today.md" ]]; then
  lines+=("Today's daily note: $today.md")
fi

moc_dir="$VAULT/00 - MOCs"
if [[ -d "$moc_dir" ]]; then
  # head closes the pipe early, which pipefail would otherwise turn into an exit.
  mocs=$(find "$moc_dir" -maxdepth 1 -name '*.md' -not -name '.*' 2>/dev/null |
    sort | head -n "$MAX_MOCS" | join_note_names || true)
  if [[ -n "$mocs" ]]; then
    lines+=("Vault MOCs: $mocs")
  fi
fi

# Skip dot-named entries below the root, as Obsidian does; -path '*/.*' would hide a whole vault under ~/.vaults.
# xargs -r: GNU xargs would otherwise run a bare `ls -t` on the working directory when find matches nothing.
recent=$(find "$VAULT" -mindepth 1 -maxdepth 3 -name '.*' -prune -o -name '*.md' -type f -print0 2>/dev/null |
  xargs -0 -r ls -t 2>/dev/null | head -n "$MAX_RECENT" | join_note_names || true)
if [[ -n "$recent" ]]; then
  lines+=("Recently modified: $recent")
fi

if ((${#lines[@]} == 0)); then
  exit 0
fi

context=$(printf '%s\n' "${lines[@]}")
if ((${#context} > MAX_CHARS)); then
  context="${context:0:MAX_CHARS}
… (truncated)"
fi
jq -n --arg context "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $context}}'
