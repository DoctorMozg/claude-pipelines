#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'CLAUDE.md')"
cat >'CLAUDE.md' <<'MD'
# web-app

## Build

- `npm run build` builds the production bundle.
- `pnpm test` runs the unit tests.
- `pnpm lint` runs ESLint.
MD
