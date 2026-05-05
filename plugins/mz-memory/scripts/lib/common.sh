#!/usr/bin/env bash
# Shared helpers for mz-memory hook scripts. Source from a parent script:
#
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/lib/common.sh"
#
# All functions here must remain exit-code-clean: callers `set -euo pipefail`
# and depend on these returning 0 even when the underlying operation no-ops.

MZ_MEMORY_VERSION="v2"
MZ_PIN_START="<!-- mz-pinned-start -->"
MZ_PIN_END="<!-- mz-pinned-end -->"
MZ_LOG_START="<!-- mz-log-start -->"
MZ_LOG_END="<!-- mz-log-end -->"

# Walk up from CLAUDE_PROJECT_DIR (or PWD) to the nearest .git, so monorepo
# subdirectories share one MEMORY.md at the repo root. MZ_MEMORY_ROOT wins
# unconditionally when set.
find_project_root() {
  if [[ -n "${MZ_MEMORY_ROOT:-}" ]]; then
    printf '%s\n' "$MZ_MEMORY_ROOT"
    return 0
  fi
  local dir="${CLAUDE_PROJECT_DIR:-$PWD}"
  dir=$(cd "$dir" 2>/dev/null && pwd) || dir="$PWD"
  while [[ "$dir" != "/" && -n "$dir" ]]; do
    if [[ -e "$dir/.git" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir=$(dirname "$dir")
  done
  printf '%s\n' "${CLAUDE_PROJECT_DIR:-$PWD}"
}

# Strip <private>...</private> regions from stdin and collapse the resulting
# adjacent whitespace so "is <private>X</private> ok" becomes "is ok", not
# "is  ok". Multi-line aware via perl; falls back to single-line sed otherwise.
strip_private() {
  if command -v perl >/dev/null 2>&1; then
    perl -0777 -pe 's|<private>.*?</private>||gs; s|[ \t]+| |g; s|[ \t]+$||mg'
  else
    sed -E 's|<private>[^<]*</private>||g; s|[ \t]+| |g; s|[ \t]+$||'
  fi
}

# atomic_write <target> — read stdin, write to a sibling tempfile, rename.
# Avoids partial files if the hook is killed by the harness timeout.
atomic_write() {
  local target="$1"
  local dir tmp
  dir=$(dirname "$target")
  tmp=$(mktemp "${dir}/.mz-memory.XXXXXX") || return 1
  cat > "$tmp"
  mv -f "$tmp" "$target"
}

# Seed MEMORY.md with the v2 layout if missing. Migrate v1 (flat list) → v2
# (Pinned + Activity Log sections with marker comments). Re-seed the header
# if the marker was hand-removed so prepend operations stay safe.
ensure_memory_file() {
  local memory_file="$1"
  local memory_dir
  memory_dir=$(dirname "$memory_file")
  mkdir -p "$memory_dir"

  if [[ ! -f "$memory_file" ]]; then
    _write_fresh_memory "$memory_file"
    return 0
  fi

  local has_version has_log has_pin
  grep -qF "mz-memory:${MZ_MEMORY_VERSION}" "$memory_file" && has_version=1 || has_version=0
  grep -qF "$MZ_LOG_START" "$memory_file" && has_log=1 || has_log=0
  grep -qF "$MZ_PIN_START" "$memory_file" && has_pin=1 || has_pin=0

  if [[ "$has_version" == 1 && "$has_log" == 1 && "$has_pin" == 1 ]]; then
    return 0
  fi

  # Header-only loss: structure intact, just the version marker is missing
  # (e.g. user hand-edited the comment block). Re-emit the header without
  # touching the body — the Pinned/Log markers are still anchoring inserts.
  if [[ "$has_log" == 1 && "$has_pin" == 1 ]]; then
    local body_no_header
    body_no_header=$(awk '
      /^# Project Memory[[:space:]]*$/ { skip = 1; next }
      /^<!-- Auto-managed by mz-memory/ { next }
      /^<!-- Entries below are auto-managed/ { next }
      /^<!-- mz-memory:/ { next }
      skip && /^[[:space:]]*$/ { skip = 0; next }
      { skip = 0; print }
    ' "$memory_file")
    {
      _emit_memory_header
      printf '%s\n' "$body_no_header"
    } | atomic_write "$memory_file"
    return 0
  fi

  # Salvage existing content into the v2 layout. Bullet lines become Activity
  # Log entries; everything non-bullet, non-header keeps its place under Pinned.
  local existing pinned_existing log_existing
  existing=$(cat "$memory_file")
  pinned_existing=$(printf '%s\n' "$existing" | awk '
    /^# / { next }
    /^<!--/ { next }
    /^## / { next }
    /^- / { next }
    /^[[:space:]]*$/ { next }
    { print }
  ')
  log_existing=$(printf '%s\n' "$existing" | grep -E '^- ' || true)

  {
    _emit_memory_header
    printf '## Pinned\n\n'
    printf '%s\n' "$MZ_PIN_START"
    [[ -n "$pinned_existing" ]] && printf '%s\n' "$pinned_existing"
    printf '%s\n\n' "$MZ_PIN_END"
    printf '## Activity Log\n\n'
    printf '%s\n' "$MZ_LOG_START"
    [[ -n "$log_existing" ]] && printf '%s\n' "$log_existing"
    printf '%s\n' "$MZ_LOG_END"
  } | atomic_write "$memory_file"
}

_write_fresh_memory() {
  local memory_file="$1"
  {
    _emit_memory_header
    printf '## Pinned\n\n'
    printf '%s\n' "$MZ_PIN_START"
    printf '%s\n\n' "$MZ_PIN_END"
    printf '## Activity Log\n\n'
    printf '%s\n' "$MZ_LOG_START"
    printf '%s\n' "$MZ_LOG_END"
  } > "$memory_file"
}

_emit_memory_header() {
  printf '# Project Memory\n\n'
  printf '<!-- Auto-managed by mz-memory. Most recent first. -->\n'
  printf '<!-- mz-memory:%s -->\n\n' "$MZ_MEMORY_VERSION"
}

# Extract the Pinned region (between marker comments). Empty string if the
# region is absent (caller already ran ensure_memory_file in normal flow).
extract_pinned() {
  local memory_file="$1"
  awk -v start="$MZ_PIN_START" -v end="$MZ_PIN_END" '
    $0 == start { capture = 1; next }
    $0 == end { capture = 0 }
    capture { print }
  ' "$memory_file"
}

# Extract the Activity Log region, capped at $2 lines (most recent first).
extract_log() {
  local memory_file="$1"
  local max_lines="${2:-200}"
  awk -v start="$MZ_LOG_START" -v end="$MZ_LOG_END" '
    $0 == start { capture = 1; next }
    $0 == end { capture = 0 }
    capture { print }
  ' "$memory_file" | head -n "$max_lines"
}

# Prepend a block of pre-formatted entries into the Activity Log region and
# prune to MAX_LOG_LINES. Block is taken from stdin so callers can pipe.
prepend_to_log() {
  local memory_file="$1"
  local max_lines="${2:-200}"
  local new_block
  new_block=$(cat)
  [[ -n "$new_block" ]] || return 0

  awk -v start="$MZ_LOG_START" -v end="$MZ_LOG_END" \
      -v new="$new_block" -v max="$max_lines" '
    BEGIN { in_log = 0; count = 0 }
    $0 == start {
      print
      printf "%s\n", new
      in_log = 1
      next
    }
    $0 == end { in_log = 0; print; next }
    in_log {
      count++
      if (count > max) next
    }
    { print }
  ' "$memory_file" | atomic_write "$memory_file"
}

# Prepend a block of pre-formatted entries into the Pinned region. No prune
# — pinned entries are user-managed; if the user pins too many, that's their
# problem to solve. Block from stdin.
prepend_to_pinned() {
  local memory_file="$1"
  local new_block
  new_block=$(cat)
  [[ -n "$new_block" ]] || return 0

  awk -v start="$MZ_PIN_START" -v new="$new_block" '
    $0 == start {
      print
      printf "%s\n", new
      next
    }
    { print }
  ' "$memory_file" | atomic_write "$memory_file"
}
