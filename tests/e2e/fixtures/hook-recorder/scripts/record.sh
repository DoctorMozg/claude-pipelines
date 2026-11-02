#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook with no matcher: appends `source=<startup|resume|clear|compact>` and prints nothing.
source=$(jq -r '.source // "unknown"' 2>/dev/null || echo unknown)
dir="${CLAUDE_PROJECT_DIR:-$PWD}/.hook-recorder"
mkdir -p "$dir"
printf 'source=%s\n' "$source" >> "$dir/sessionstart.log"
