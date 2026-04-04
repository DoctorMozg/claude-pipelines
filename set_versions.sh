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

# Update marketplace.json (metadata.version + all plugin versions)
sed -i "s/\"version\": \"[0-9]*\.[0-9]*\.[0-9]*\"/\"version\": \"$VERSION\"/g" \
    "$REPO_ROOT/.claude-plugin/marketplace.json"

# Update all plugin.json files
for f in "$REPO_ROOT"/plugins/*/plugin.json; do
    sed -i "s/\"version\": \"[0-9]*\.[0-9]*\.[0-9]*\"/\"version\": \"$VERSION\"/" "$f"
    echo "Updated: ${f#$REPO_ROOT/}"
done

# Update README.md version column
sed -i "s/| [0-9]*\.[0-9]*\.[0-9]* *|/| $VERSION   |/g" "$REPO_ROOT/README.md"

echo "Updated: .claude-plugin/marketplace.json"
echo "Updated: README.md"
echo ""
echo "All versions set to $VERSION"
