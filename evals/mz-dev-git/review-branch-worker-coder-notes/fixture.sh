#!/usr/bin/env bash
set -euo pipefail
# A final review unit whose coder notes sit outside any .mz/task/*/state.md match, as an orchestrated run leaves them.
git init -q -b main
git config user.name eval
git config user.email eval@example.invalid
mkdir -p src/util units
touch src/__init__.py src/util/__init__.py
printf '.mz/\n' >.gitignore
echo "# shop" >README.md
git add -A
git commit -q -m "init"
git branch -M main

cat >src/util/retry.py <<'PY'
import logging
import random
import time

log = logging.getLogger(__name__)

TRANSIENT_ERRORS = (ConnectionError, TimeoutError)


def retry_with_backoff(func, *, attempts=4, base_delay=0.2, max_delay=5.0, retry_on=TRANSIENT_ERRORS):
    """Call func until it succeeds, sleeping with exponential backoff and jitter between tries."""
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except retry_on as exc:
            if attempt == attempts:
                raise
            delay = min(max_delay, base_delay * 2 ** (attempt - 1)) * random.uniform(0.5, 1.0)
            log.warning("attempt %d/%d failed: %s; retrying in %.2fs", attempt, attempts, exc, delay)
            time.sleep(delay)
PY
git add -A
git commit -q -m "Add retry helper"

git checkout -q -b orch-eval-FR1-app
mkdir -p src/inventory
touch src/inventory/__init__.py
cat >src/inventory/client.py <<'PY'
import time


class InventoryClient:
    def __init__(self, transport):
        self._transport = transport

    def stock_level(self, sku):
        last_error = None
        for _ in range(5):
            try:
                return self._transport.get(f"/stock/{sku}")["available"]
            except Exception as exc:
                last_error = exc
                time.sleep(1)
        raise last_error
PY
git add -A
git commit -q -m "Add inventory client"

# The orchestrator concatenates the merged units' notes here; no task folder names this branch.
notes_dir=$PWD/.mz/orchestrate_fixture/final/repo
mkdir -p "$notes_dir"
cat >"$notes_dir/decisions.md" <<'DEC'
# Unit WU-1: Inventory client

## Fixed one-second retry loop
- Where: src/inventory/client.py:10
- Choice: stock_level retries in its own loop with a fixed one-second sleep
- Alternatives weighed: retry_with_backoff from src/util/retry.py
- Reason: The stock API enforces a one-request-per-second token bucket; retry_with_backoff jitters delays below one second, so its early retries are rejected and count against the bucket.
DEC

cat >units/FR1-app.md <<MD
# Unit FR1-app: Final review of app

- task: 2026_11_23_orchestrate_eval
- kind: review
- skill: mz-dev-git:review-branch
- owns:
- verify: true

## Spec

Base branch: main. Review every change between \`main\` and this branch's head (\`git diff main...HEAD\`). Report findings with a severity of \`critical\`, \`major\` or \`minor\`, a \`file:line\` and a one-line fix; change nothing.
Coder notes: $notes_dir/decisions.md
MD
