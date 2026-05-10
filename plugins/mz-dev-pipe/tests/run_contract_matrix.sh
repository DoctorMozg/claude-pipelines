#!/usr/bin/env bash
# Validate that every agent file documents the terminal-state tokens declared
# for it in contract_matrix.md. Exits non-zero on any failed cell.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MATRIX="$REPO_ROOT/plugins/mz-dev-pipe/tests/contract_matrix.md"

if [ ! -f "$MATRIX" ]; then
  echo "Error: matrix file not found at $MATRIX" >&2
  exit 2
fi

# Resolve an agent file by name across all installed plugins under plugins/.
# Agents may live in mz-dev-pipe/agents/ or any sister plugin. Returns the
# absolute path on stdout, empty on miss.
find_agent_file() {
  local agent_name="$1"
  find "$REPO_ROOT/plugins" -mindepth 3 -maxdepth 3 -type f \
       -path "*/agents/${agent_name}.md" -print -quit 2>/dev/null
}

# Check whether the file documents a given STATUS or VERDICT token. Accepts:
#   Form A — literal "<KIND>: <TOKEN>" line, with optional bar-separated continuation.
#   Form B — markdown list bullet of the form "- `<TOKEN>` —" within an agent that
#            also has a "<KIND>:" or "<KIND> Protocol" header (proximity guard).
agent_documents_token() {
  local file="$1"
  local kind="$2"   # STATUS or VERDICT
  local token="$3"  # DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED, PASS, FAIL

  # Form A — literal "<KIND>: ... <TOKEN>" anywhere on a single line.
  if grep -qE "${kind}:[[:space:]]+[A-Z_|[:space:]]*${token}([^A-Z_]|$)" "$file"; then
    return 0
  fi

  # Form B — backtick-quoted token name AND the file references the kind elsewhere.
  if grep -qE "(^|[^A-Z_])${kind}:|${kind}[[:space:]]+[Pp]rotocol" "$file"; then
    if grep -qE "\`${token}\`" "$file"; then
      return 0
    fi
  fi

  return 1
}

# Parse the matrix table. We expect rows of the shape:
#   | pipeline-name | X | X | . | X | . | . |
# with the header row defining the column-to-token mapping.
PASS=0
FAIL=0
MISSING_AGENTS=0

# Column order in the matrix (must match contract_matrix.md header):
COLUMN_KINDS=(STATUS STATUS STATUS STATUS VERDICT VERDICT)
COLUMN_TOKENS=(DONE DONE_WITH_CONCERNS NEEDS_CONTEXT BLOCKED PASS FAIL)
NUM_COLUMNS=${#COLUMN_TOKENS[@]}

# Read the matrix line by line, picking up only the data rows (start with
# "| pipeline-").
while IFS= read -r line; do
  [[ "$line" =~ ^\|[[:space:]]+pipeline- ]] || continue

  # Split on |, trim whitespace from each field.
  IFS='|' read -ra fields <<< "$line"
  # fields[0] is empty (leading |), fields[1] is the agent name cell.
  agent_name=$(echo "${fields[1]}" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')

  agent_file=$(find_agent_file "$agent_name")
  if [ -z "$agent_file" ]; then
    echo "MISSING_AGENT: $agent_name (no file under plugins/*/agents/)"
    MISSING_AGENTS=$((MISSING_AGENTS + 1))
    continue
  fi

  for col_idx in $(seq 0 $((NUM_COLUMNS - 1))); do
    field_idx=$((col_idx + 2))  # +1 for leading empty, +1 for agent-name col
    cell=$(echo "${fields[$field_idx]:-}" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
    [ "$cell" = "X" ] || continue

    kind="${COLUMN_KINDS[$col_idx]}"
    token="${COLUMN_TOKENS[$col_idx]}"

    if agent_documents_token "$agent_file" "$kind" "$token"; then
      PASS=$((PASS + 1))
    else
      echo "FAIL: $agent_name does not document ${kind}: ${token}"
      FAIL=$((FAIL + 1))
    fi
  done
done < "$MATRIX"

echo ""
echo "Contract matrix: $PASS passed, $FAIL failed, $MISSING_AGENTS missing agent file(s)"

if [ "$FAIL" -gt 0 ] || [ "$MISSING_AGENTS" -gt 0 ]; then
  exit 1
fi
exit 0
