#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname '.claude/rules/python-conventions.md')"
cat >'.claude/rules/python-conventions.md' <<'MD'
## Python

- Format with ruff, line length 88.
- Type every public function.
MD
