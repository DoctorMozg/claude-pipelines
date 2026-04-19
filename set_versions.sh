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

# sed -i is incompatible between GNU and BSD: GNU takes no argument, BSD
# requires a backup-extension argument (and silently treats the next flag as
# one if omitted — which is why running with -E creates *.json-E backups on
# macOS). Detect once and build the correct invocation.
if sed --version >/dev/null 2>&1; then
  SED_INPLACE=(sed -i -E)
else
  SED_INPLACE=(sed -i '' -E)
fi

# Substitute every "version": "X.Y.Z" occurrence and verify the file actually
# changed before accepting the rewrite. Fail fast on any file that was supposed
# to carry a version but didn't.
rewrite_version() {
  local file="$1"
  local expected_min="$2"

  if [ ! -f "$file" ]; then
    echo "Error: missing file $file" >&2
    exit 1
  fi

  local count
  count=$(grep -cE '"version":[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$file" || true)
  if [ "$count" -lt "$expected_min" ]; then
    echo "Error: $file has $count version field(s); expected at least $expected_min" >&2
    exit 1
  fi

  "${SED_INPLACE[@]}" "s/\"version\":[[:space:]]*\"[0-9]+\.[0-9]+\.[0-9]+\"/\"version\": \"$VERSION\"/g" "$file"
  echo "Updated: ${file#"$REPO_ROOT"/} ($count occurrence(s))"
}

# marketplace.json carries metadata.version + one version per plugin entry.
PLUGIN_COUNT=$(find "$REPO_ROOT/plugins" -mindepth 1 -maxdepth 1 -type d | wc -l)
EXPECTED_MARKETPLACE_VERSIONS=$((PLUGIN_COUNT + 1))
rewrite_version "$REPO_ROOT/.claude-plugin/marketplace.json" "$EXPECTED_MARKETPLACE_VERSIONS"

# Each plugin.json has exactly one version field.
for f in "$REPO_ROOT"/plugins/*/plugin.json; do
  rewrite_version "$f" 1
done

echo ""
echo "All versions set to $VERSION"
