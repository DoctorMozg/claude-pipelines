#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.2.0"
  exit 1
fi

VERSION="$1"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must be semver (e.g., 0.2.0)"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Precondition — agent contract matrix must pass before any version bump.
# A drifted terminal-state token in any agent file would silently break an
# orchestrator branch; we'd rather fail the bump than ship the drift.
CONTRACT_MATRIX="$REPO_ROOT/plugins/mz-dev-pipe/tests/run_contract_matrix.sh"
if [ -x "$CONTRACT_MATRIX" ]; then
  MATRIX_OUT=$(mktemp)
  trap 'rm -f "$MATRIX_OUT"' EXIT
  if ! "$CONTRACT_MATRIX" >"$MATRIX_OUT" 2>&1; then
    echo "Error: contract matrix failed — version bump blocked." >&2
    cat "$MATRIX_OUT" >&2
    exit 1
  fi
fi

# sed -i is incompatible between GNU and BSD: GNU takes no argument, BSD
# requires a backup-extension argument (and silently treats the next flag as
# one if omitted — which is why running with -E creates *.json-E backups on
# macOS). Detect once and build the correct invocation.
if sed --version >/dev/null 2>&1; then
  SED_INPLACE=(sed -i -E)
else
  SED_INPLACE=(sed -i '' -E)
fi

# The marketplace keeps only metadata.version; plugin versions live in each manifest, which wins at install time.
VERSION_FILES=("$REPO_ROOT/.claude-plugin/marketplace.json")
for dir in "$REPO_ROOT"/plugins/*/; do
  VERSION_FILES+=("${dir}.claude-plugin/plugin.json")
done
VERSION_PATTERN='"version":[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"'

# Check every file before rewriting any, so drift in one file never leaves a half-bumped repo.
for file in "${VERSION_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Error: missing file $file" >&2
    exit 1
  fi
  count=$(grep -cE "$VERSION_PATTERN" "$file" || true)
  if [ "$count" -ne 1 ]; then
    echo "Error: $file has $count version field(s); expected exactly 1" >&2
    exit 1
  fi
done

for file in "${VERSION_FILES[@]}"; do
  "${SED_INPLACE[@]}" "s/${VERSION_PATTERN}/\"version\": \"$VERSION\"/" "$file"
  echo "Updated: ${file#"$REPO_ROOT"/}"
done

echo ""
echo "All versions set to $VERSION"
