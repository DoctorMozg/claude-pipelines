#!/usr/bin/env bash
# Shared helpers for the handoff hooks and handoff-facts.sh.

# Walk up from CLAUDE_PROJECT_DIR (or the working directory) to the nearest .git, so .mz/ is the
# one mz-memory uses; MZ_MEMORY_ROOT wins when set. Kept identical to mz-memory's lib/common.sh.
find_project_root() {
  if [[ -n "${MZ_MEMORY_ROOT:-}" ]]; then
    printf '%s\n' "$MZ_MEMORY_ROOT"
    return 0
  fi
  local dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  dir=$(cd "$dir" 2>/dev/null && pwd) || dir=$(pwd)
  while [[ "$dir" != "/" && -n "$dir" ]]; do
    if [[ -e "$dir/.git" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir=$(dirname "$dir")
  done
  printf '%s\n' "${CLAUDE_PROJECT_DIR:-$(pwd)}"
}

MZ_HANDOFF_DEFAULT_AFTER=3
# The marker Claude Code writes to the main transcript once per compaction of the main conversation.
MZ_HANDOFF_BOUNDARY='"subtype":"compact_boundary"'

# MZ_HANDOFF_AFTER compactions trigger the handoff; 0 turns it off.
handoff_threshold() {
  local value="${MZ_HANDOFF_AFTER:-$MZ_HANDOFF_DEFAULT_AFTER}"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "mz-handoff: MZ_HANDOFF_AFTER=${value} is not a whole number, using ${MZ_HANDOFF_DEFAULT_AFTER}" >&2
    value="$MZ_HANDOFF_DEFAULT_AFTER"
  fi
  printf '%s\n' "$((10#$value))"
}

# Subagent compactions land in <session>/subagents/, so this counts the main conversation only.
compaction_count() {
  grep -c -F -- "$MZ_HANDOFF_BOUNDARY" "$1" 2>/dev/null || true
}

# The claude process is an ancestor of every hook and Bash call and stays the same across /clear.
claude_pid() {
  local pid=$$ comm hops=0
  while [[ -n "$pid" && "$pid" -gt 1 && "$hops" -lt 12 ]]; do
    comm=$(ps -o comm= -p "$pid" 2>/dev/null || true)
    comm="${comm##*/}"
    if [[ "$comm" == "claude" || "$comm" == "node" ]]; then
      printf '%s\n' "$pid"
      return 0
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    hops=$((hops + 1))
  done
  return 0
}

# handoff_field <file> <key>: a value from the file's leading --- frontmatter block.
handoff_field() {
  awk -v key="$2" '
    NR == 1 { if ($0 != "---") exit; next }
    $0 == "---" { exit }
    index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }
  ' "$1" 2>/dev/null || true
}

# handoff_files <dir> [max_age_minutes]: handoff files, newest first.
handoff_files() {
  local dir="$1" age="${2:-}" files=() file
  [[ -d "$dir" ]] || return 0
  # A while-read loop rather than mapfile, which the bash 3.2 that ships with macOS lacks.
  while IFS= read -r file; do
    files+=("$file")
  done < <(
    if [[ -n "$age" ]]; then
      find "$dir" -maxdepth 1 -type f -name '*.md' -mmin "-${age}" 2>/dev/null
    else
      find "$dir" -maxdepth 1 -type f -name '*.md' 2>/dev/null
    fi
  )
  [[ ${#files[@]} -gt 0 ]] || return 0
  ls -t -- "${files[@]}" 2>/dev/null || true
}

# The newest handoff this session wrote, if any.
handoff_for_session() {
  local file
  while IFS= read -r file; do
    if [[ "$(handoff_field "$file" session_id)" == "$2" ]]; then
      printf '%s\n' "$file"
      return 0
    fi
  done < <(handoff_files "$1")
  return 0
}

# The first line of text under a "## <heading>" in a handoff body.
handoff_section_head() {
  awk -v heading="## $2" '
    $0 == heading { inside = 1; next }
    inside && /^## / { exit }
    inside && NF { print; exit }
  ' "$1" 2>/dev/null || true
}
