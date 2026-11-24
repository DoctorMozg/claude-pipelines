#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'Brain/CLAUDE.md')"
cat >'Brain/CLAUDE.md' <<'MD'
# Brain

Personal vault. Notes are atomic, one idea each.

## Do's

- Link every new note to at least one existing note.

## Don'ts

- Don't rename a note without updating its backlinks.
- Don't paste whole articles; summarize and link.
MD
