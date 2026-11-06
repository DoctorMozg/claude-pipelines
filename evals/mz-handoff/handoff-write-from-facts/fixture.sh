#!/usr/bin/env bash
set -euo pipefail
# The handoff scripts resolve the project root to the nearest .git, and the eval HOME is a git repo.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
mkdir -p src
printf 'def backoff(attempt):\n    return 2 ** attempt\n' > src/retry.py
git add src/retry.py
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add retry backoff"
mkdir -p .mz/task/2026_11_05_build_retry
cat > .mz/task/2026_11_05_build_retry/state.md <<'STATE'
# 2026_11_05_build_retry

Status: running
Phase: 3

## Decisions
- Exponential backoff with a 30 s cap
STATE
