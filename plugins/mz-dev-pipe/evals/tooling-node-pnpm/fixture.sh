#!/usr/bin/env bash
set -euo pipefail
# detect-tooling resolves the project root to the nearest .git, and the eval's HOME is a git repo.
git init -q
cat > package.json <<'JSON'
{"name": "web", "private": true,
 "devDependencies": {"vitest": "^2.1.0", "eslint": "^9.0.0", "prettier": "^3.3.0", "typescript": "^5.6.0"}}
JSON
touch pnpm-lock.yaml
