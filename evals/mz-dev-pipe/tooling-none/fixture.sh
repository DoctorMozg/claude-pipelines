#!/usr/bin/env bash
set -euo pipefail
# detect-tooling resolves the project root to the nearest .git, and the eval's HOME is a git repo.
git init -q
printf '# notes\n' > README.md
