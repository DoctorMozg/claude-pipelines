#!/usr/bin/env bash
set -euo pipefail
# A feature branch hand-rolls a fixed-delay retry loop. Two earlier build tasks recorded the branch: one started at the merge-base (in range), one before it (a reused branch name from an older run).
git init -q -b main
git config user.name eval
git config user.email eval@example.invalid
mkdir -p src/util
touch src/__init__.py src/util/__init__.py
echo ".mz/" >.gitignore
echo "# shop" >README.md
git add -A
git commit -q -m "init"
git branch -M main
OLD_MAIN=$(git rev-parse HEAD)

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
BASE=$(git rev-parse HEAD)
# The base branch is main, so the merge-base is $BASE and $OLD_MAIN lies before it.

git checkout -q -b feature/inventory-client
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

write_task() {
  local name=$1 start=$2 reason=$3
  local dir=".mz/task/$name"
  mkdir -p "$dir"
  cat >"$dir/state.md" <<STATE
schema_version: 2
Status: complete
Phase: complete
Started: 2026-11-20
Iteration: 1
FilesWritten:
  - .mz/task/$name/decisions.md
phase_complete: true
what_remains: []
Branch: feature/inventory-client
StartCommit: $start
STATE
  cat >"$dir/decisions.md" <<DEC
## Fixed one-second retry loop
- Where: src/inventory/client.py:10
- Choice: stock_level retries in its own loop with a fixed one-second sleep
- Alternatives weighed: retry_with_backoff from src/util/retry.py
- Reason: $reason
DEC
}

write_task 2026_11_20_build_inventory_zebra "$BASE" \
  "The stock API enforces a one-request-per-second token bucket; retry_with_backoff jitters delays below one second, so its early retries are rejected and count against the bucket."
write_task 2026_08_03_build_inventory_walrus "$OLD_MAIN" \
  "A previous inventory client on this branch name needed a fixed delay because the vendor SDK refused concurrent calls."

# The stale task must fail the range check, the matching one must pass it.
git merge-base --is-ancestor "$BASE" "$BASE"
! git merge-base --is-ancestor "$BASE" "$OLD_MAIN"
