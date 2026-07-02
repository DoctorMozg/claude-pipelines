#!/usr/bin/env bash
# Static smoke test for the /build pipeline plumbing.
#
# True end-to-end smoke would invoke Claude against the fixture/ repo and
# assert STATUS-line emission from every dispatched agent. That requires
# either a mocked agent harness or a paid Claude API call — neither suitable
# for a Makefile-driven CI gate. Instead, this script statically validates:
#
#   1. Every agent referenced by build/SKILL.md and its phases has a file.
#   2. Every shared/ reference resolves to a real file.
#   3. The contract matrix passes for all dispatched agents.
#   4. The fixture/ repo is well-formed (parses as Python).
#   5. No skill writes a non-enum state Status token (the schema enum is
#      pending|running|complete|aborted_by_user|failed; resume-protocol
#      branches on exact tokens, so `completed`/`in_progress` break resume).
#
# Result is written to .mz/metrics/smoke/<date>.json so CI can compare runs
# over time.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BUILD_SKILL="$REPO_ROOT/plugins/mz-dev-pipe/skills/build"
AGENTS_DIRS=("$REPO_ROOT/plugins/mz-dev-pipe/agents" "$REPO_ROOT/plugins/mz-research-pipe/agents")
SHARED_DIR="$REPO_ROOT/plugins/mz-dev-pipe/skills/shared"
FIXTURE_DIR="$REPO_ROOT/plugins/mz-dev-pipe/tests/smoke/fixture"
METRICS_DIR="$REPO_ROOT/.mz/metrics/smoke"
TODAY="$(date +%Y_%m_%d)"
REPORT="$METRICS_DIR/${TODAY}.json"

mkdir -p "$METRICS_DIR"

PASS=0
FAIL=0
FAILURES=()

record_pass() {
  PASS=$((PASS + 1))
}
record_fail() {
  FAIL=$((FAIL + 1))
  FAILURES+=("$1")
  echo "FAIL: $1"
}

# --- Check 1: every pipeline-* agent referenced by build/ has a file --------
agents_referenced=$(grep -hoE "pipeline-[a-z-]+" "$BUILD_SKILL/SKILL.md" "$BUILD_SKILL/phases/"*.md | sort -u)
for agent in $agents_referenced; do
  found=""
  for d in "${AGENTS_DIRS[@]}"; do
    if [ -f "$d/$agent.md" ]; then
      found="$d/$agent.md"
      break
    fi
  done
  if [ -n "$found" ]; then
    record_pass
  else
    record_fail "agent file missing: $agent (referenced by build/)"
  fi
done

# --- Check 2: every shared/ link resolves -----------------------------------
shared_links=$(grep -hoE "shared/[a-z-]+\.md" "$BUILD_SKILL/SKILL.md" "$BUILD_SKILL/phases/"*.md | sort -u)
for link in $shared_links; do
  base=$(basename "$link")
  if [ -f "$SHARED_DIR/$base" ]; then
    record_pass
  else
    record_fail "shared file missing: $link (referenced by build/)"
  fi
done

# --- Check 3: contract matrix still passes ----------------------------------
if "$REPO_ROOT/plugins/mz-dev-pipe/tests/run_contract_matrix.sh" >/tmp/smoke_matrix.out 2>&1; then
  record_pass
else
  record_fail "contract matrix failed (see /tmp/smoke_matrix.out)"
fi
rm -f /tmp/smoke_matrix.out

# --- Check 4: fixture parses as Python --------------------------------------
if command -v python3 >/dev/null 2>&1; then
  for f in "$FIXTURE_DIR"/*.py; do
    if python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
      record_pass
    else
      record_fail "fixture file does not parse: $(basename "$f")"
    fi
  done
else
  echo "WARN: python3 not on PATH, skipping fixture parse check"
fi

# --- Check 5: no non-enum state Status tokens in skill files ----------------
SKILLS_DIR="$REPO_ROOT/plugins/mz-dev-pipe/skills"
bad_status=$(grep -rn -E 'Status:?[[:space:]]*`?(completed|in_progress|complete_with_residuals)`?|status to `(completed|in_progress)`' \
  "$SKILLS_DIR" --include='*.md' \
  | grep -v 'shared/state-schema.md' \
  | grep -v 'shared/resume-protocol.md' \
  || true)
if [ -z "$bad_status" ]; then
  record_pass
else
  record_fail "non-enum Status tokens found: $(echo "$bad_status" | head -5 | tr '\n' ';')"
fi

# --- Write JSON report -----------------------------------------------------
{
  echo '{'
  printf '  "date": "%s",\n' "$TODAY"
  printf '  "passed": %d,\n' "$PASS"
  printf '  "failed": %d,\n' "$FAIL"
  printf '  "failures": ['
  if [ "${#FAILURES[@]}" -gt 0 ]; then
    sep=""
    for msg in "${FAILURES[@]}"; do
      printf '%s\n    "%s"' "$sep" "${msg//\"/\\\"}"
      sep=","
    done
    printf '\n  '
  fi
  echo ']'
  echo '}'
} > "$REPORT"

echo ""
echo "Smoke test: $PASS passed, $FAIL failed"
echo "Report: ${REPORT#"$REPO_ROOT"/}"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
