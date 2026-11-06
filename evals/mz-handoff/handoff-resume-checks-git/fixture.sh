#!/usr/bin/env bash
set -euo pipefail
# The handoff scripts resolve the project root to the nearest .git, and the eval HOME is a git repo.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
mkdir -p src .mz/handoff
printf 'def backoff(attempt):\n    return 2 ** attempt\n' > src/retry.py
git add src/retry.py
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add retry backoff"
head=$(git rev-parse --short HEAD)
cat > .mz/handoff/2026_11_05_1830_aaaaaaaa.md <<HANDOFF
---
schema: handoff/1
session_id: aaaaaaaa-0000-0000-0000-000000000000
claude_pid: 1
transcript: /nonexistent/aaaaaaaa.jsonl
written_at: 2026-11-05T18:30:00Z
compactions: 3
cwd: $PWD
branch: $(git rev-parse --abbrev-ref HEAD)
head: ${head}
task: none
status: open
---
## Goal
Add retries with exponential backoff to the HTTP client. Done when src/retry.py caps the delay.

## Constraints (verbatim)
> "Never push to origin without asking me first" (user, 2026-11-05T17:40)

## Done (verified)
- Backoff function. Evidence: commit ${head}

## Next
1. Cap the delay at 30 seconds in src/retry.py

## Verify on resume
- \`test -f src/retry.py && echo ok\` → ok
HANDOFF
printf 'import random\n\ndef jitter(delay):\n    return delay * random.random()\n' >> src/retry.py
git add src/retry.py
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add jitter to retry delays"
