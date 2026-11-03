#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook (Write|Edit on *.md): fixes a vault note's Obsidian frontmatter in place, like a formatter.
# The rules and the YAML subset live in lib/frontmatter-normalize.awk; a note outside that subset is left alone.

[[ "${MZ_FRONTMATTER_NORMALIZE:-1}" != 0 ]] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[[ "$file" == /*.md && "$file/" != */../* && -f "$file" && ! -L "$file" && -w "$file" ]] || exit 0

vault=""
configured=${OBSIDIAN_VAULT_PATH:-${MZ_VAULT_PATH:-}}
configured=${configured%/}
if [[ -n "$configured" && "$file" == "$configured"/* ]]; then
  vault=$configured
else
  dir=${file%/*}
  while [[ -n "$dir" ]]; do
    if [[ -d "$dir/.obsidian" ]]; then
      vault=$dir
      break
    fi
    dir=${dir%/*}
  done
fi
[[ -n "$vault" ]] || exit 0

rel=${file#"$vault"/}
[[ "/$rel" != */.* ]] || exit 0

# Notes in the templates folder of core Templates or Templater are skipped, so no date is baked into a template.
template_configs=()
for config in "$vault/.obsidian/templates.json" "$vault/.obsidian/plugins/templater-obsidian/data.json"; do
  [[ -f "$config" ]] && template_configs+=("$config")
done
if ((${#template_configs[@]})); then
  while IFS= read -r folder; do
    folder=${folder#/}
    folder=${folder%/}
    if [[ -n "$folder" && "$rel" == "$folder"/* ]]; then
      echo "frontmatter-normalize: skipped template $rel" >&2
      exit 0
    fi
  done < <(jq -r '(.folder // .templates_folder // empty) | strings' "${template_configs[@]}" 2>/dev/null || true)
fi

schema="$vault/.mz/vault-schema.yml"
[[ -f "$schema" ]] || schema=/dev/null

status=0
out=$(awk -v schema_file="$schema" -v today="$(date +%F)" -v max_lines=200 \
  -f "$(dirname "$0")/lib/frontmatter-normalize.awk" "$schema" "$file") || status=$?
if ((status == 2)); then
  echo "frontmatter-normalize: left $rel untouched: $out" >&2
fi
((status == 0)) || exit 0

closing=${out%%$'\n'*}
out=${out#*$'\n'}
changes=${out%%$'\n'*}
frontmatter=${out#*$'\n'}

# cp -p carries the note's mode over to the temp file, and the rewrite into it keeps that mode.
write_note() {
  new=$(mktemp "${file%/*}/.frontmatter-normalize.XXXXXX") &&
    cp -p -- "$file" "$new" &&
    {
      printf -- '---\n%s\n' "$frontmatter"
      tail -n +"$closing" -- "$file"
    } >"$new" &&
    mv -f -- "$new" "$file"
}

new=""
trap 'rm -f -- "$new"' EXIT
if ! write_note; then
  echo "frontmatter-normalize: could not rewrite $rel" >&2
  exit 0
fi

jq -n --arg context "frontmatter-normalize: $changes in $rel. Re-read it before editing." \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $context}}'
