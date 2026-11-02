#!/usr/bin/env bash
# Shared helpers for mz-memory hook scripts. Source from a parent script:
#
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/lib/common.sh"
#
# All functions here must remain exit-code-clean: callers `set -euo pipefail`
# and depend on these returning 0 even when the underlying operation no-ops.

# Inside the curator's own claude -p child every mz-memory hook is a no-op.
[[ "${MZ_MEMORY_CURATOR:-}" == "1" ]] && exit 0

MZ_MEMORY_VERSION="v2"
MZ_PIN_START="<!-- mz-pinned-start -->"
MZ_PIN_END="<!-- mz-pinned-end -->"
MZ_LOG_START="<!-- mz-log-start -->"
MZ_LOG_END="<!-- mz-log-end -->"
# The Digest sits between Pinned and the Activity Log; the first compression creates it.
MZ_DIGEST_START="<!-- mz-digest-start -->"
MZ_DIGEST_END="<!-- mz-digest-end -->"
# The stored Activity Log is capped in lines. Compression starts below the cap so old lines
# are summarized before pruning would drop them.
MZ_LOG_MAX_LINES=400
# shellcheck disable=SC2034 # read by memory-capture.sh and memory-compress.sh, which source this file
MZ_COMPRESS_THRESHOLD=300

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

_memory_region() {
  awk -v start="$2" -v end="$3" '
    $0 == start { capture = 1; next }
    $0 == end { capture = 0 }
    capture { print }
  ' "$1"
}

# Extract the Pinned region (between marker comments). Empty string if the
# region is absent (caller already ran ensure_memory_file in normal flow).
extract_pinned() {
  _memory_region "$1" "$MZ_PIN_START" "$MZ_PIN_END"
}

# Extract the Activity Log region, capped at $2 lines (most recent first).
extract_log() {
  _memory_region "$1" "$MZ_LOG_START" "$MZ_LOG_END" | head -n "${2:-200}" || true
}

# Extract the Digest items, highest count first. Empty until a compression has produced one.
extract_digest() {
  _memory_region "$1" "$MZ_DIGEST_START" "$MZ_DIGEST_END" | awk 'NF' || true
}

# Prepend entries from stdin to the Activity Log and prune it to $2 lines, new entries included.
# Holds the MEMORY.md lock, so a compression applying its result cannot overwrite these entries.
prepend_to_log() {
  local memory_file="$1"
  local max_lines="${2:-$MZ_LOG_MAX_LINES}"
  local new_block
  new_block=$(cat)
  [[ -n "$new_block" ]] || return 0

  {
    flock 9 2>/dev/null || true
    # ENVIRON, unlike awk -v, keeps backslashes in entries literal.
    MZ_NEW_BLOCK="$new_block" awk -v start="$MZ_LOG_START" -v end="$MZ_LOG_END" -v max="$max_lines" '
      BEGIN { in_log = 0; new = ENVIRON["MZ_NEW_BLOCK"]; count = split(new, new_lines, "\n") }
      $0 == start {
        print
        for (i = 1; i <= count && i <= max; i++) print new_lines[i]
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
  } 9>>"${memory_file}.lock"
}

# Prepend a block of pre-formatted entries into the Pinned region. No prune
# — pinned entries are user-managed; if the user pins too many, that's their
# problem to solve. Block from stdin.
prepend_to_pinned() {
  local memory_file="$1"
  local new_block
  new_block=$(cat)
  [[ -n "$new_block" ]] || return 0

  {
    flock 9 2>/dev/null || true
    MZ_NEW_BLOCK="$new_block" awk -v start="$MZ_PIN_START" '
      $0 == start { print; print ENVIRON["MZ_NEW_BLOCK"]; next }
      { print }
    ' "$memory_file" | atomic_write "$memory_file"
  } 9>>"${memory_file}.lock"
}

# swap_digest_and_log <memory_file> <digest_file> <log_file> — print MEMORY.md with the Digest and
# the Activity Log replaced by the two files' lines. The caller holds the lock and writes the result.
swap_digest_and_log() {
  local memory_file="$1" digest_file="$2" log_file="$3"
  local has_digest=0 want_digest=0
  grep -qxF "$MZ_DIGEST_START" "$memory_file" && has_digest=1
  [[ -s "$digest_file" ]] && want_digest=1
  awk -v ds="$MZ_DIGEST_START" -v de="$MZ_DIGEST_END" -v ls="$MZ_LOG_START" -v le="$MZ_LOG_END" \
    -v digest_file="$digest_file" -v log_file="$log_file" \
    -v has_digest="$has_digest" -v want_digest="$want_digest" '
    function dump(path,   line) { while ((getline line < path) > 0) print line; close(path) }
    $0 == ds { print; dump(digest_file); in_digest = 1; next }
    in_digest && $0 == de { in_digest = 0; print; next }
    in_digest { next }
    # A file without a Digest gets one just above the Activity Log heading, or its marker.
    !has_digest && want_digest && !inserted && ($0 == "## Activity Log" || $0 == ls) {
      printf "## Digest\n\n%s\n", ds
      dump(digest_file)
      printf "%s\n\n", de
      inserted = 1
    }
    $0 == ls { print; dump(log_file); in_log = 1; next }
    in_log && $0 == le { in_log = 0; print; next }
    in_log { next }
    { print }
  ' "$memory_file"
}

# --- Interaction journal (.mz/journal.md) ------------------------------------
# The journal is an append-only record of AskUserQuestion calls and skill entries.
# MEMORY.md is fed from state.md, not from the journal.

# Replace <private>...</private> regions with [redacted] WITHOUT collapsing the
# surrounding whitespace — verbatim journal artifacts must keep their code
# indentation and blank lines (unlike strip_private, which collapses spaces).
redact_private() {
  if command -v perl >/dev/null 2>&1; then
    perl -0777 -pe 's|<private>.*?</private>|[redacted]|gs'
  else
    sed -E 's|<private>[^<]*</private>|[redacted]|g'
  fi
}

# Seed the journal with a header if it does not exist yet.
ensure_journal_file() {
  local journal_file="$1"
  local journal_dir
  journal_dir=$(dirname "$journal_file")
  mkdir -p "$journal_dir"
  [[ -f "$journal_file" ]] && return 0
  {
    printf '# Interaction Journal\n\n'
    printf '<!-- Auto-managed by mz-memory journal-capture. Append-only, newest last. -->\n'
    printf '<!-- Append-only interaction journal. Not read for recall. -->\n\n'
  } >"$journal_file"
}

# Append a pre-formatted markdown block (read from stdin) to the journal, after
# redacting <private> regions. Serializes concurrent writers with flock when
# available; degrades to a plain append if flock is missing. No-op on empty
# input. Always returns 0 so a logging failure never derails the caller.
journal_append() {
  local journal_file="$1"
  local block
  block=$(cat)
  [[ -n "$block" ]] || return 0
  ensure_journal_file "$journal_file"
  block=$(printf '%s' "$block" | redact_private)
  {
    flock 9 2>/dev/null || true
    printf '%s\n\n' "$block" >>"$journal_file"
  } 9>>"${journal_file}.lock"
}
