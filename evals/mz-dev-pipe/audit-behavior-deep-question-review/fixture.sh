#!/usr/bin/env bash
set -euo pipefail
# Deep audit diffs the branch against origin/main, so the base commit gets that ref.
git init -q -b main
mkdir -p shop/util shop/clients
cat >shop/__init__.py <<'EOF'
EOF
cat >shop/util/__init__.py <<'EOF'
EOF
cat >shop/clients/__init__.py <<'EOF'
EOF
cat >shop/util/retry.py <<'EOF'
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(call: Callable[[], T], attempts: int = 4, base_delay: float = 0.2) -> T:
    """Run call, retrying on ConnectionError with jittered exponential backoff."""
    for attempt in range(attempts):
        try:
            return call()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
            time.sleep(base_delay * 2**attempt + random.uniform(0, base_delay))
    raise AssertionError("unreachable")
EOF
cat >shop/clients/inventory.py <<'EOF'
from shop.util.retry import retry_with_backoff


def stock_level(session, sku: str) -> int:
    return retry_with_backoff(lambda: session.get(f"/inventory/{sku}").json()["level"])
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Inventory client with shared retry helper"
# The workspace may already be a repository, where init's -b is ignored, so name the branch explicitly.
git branch -M main
git update-ref refs/remotes/origin/main main
git checkout -q -b pricing-client
# The questionable choice: a hand-rolled fixed-delay retry loop next to the repo's backoff helper.
cat >shop/clients/pricing.py <<'EOF'
import time


def current_price(session, sku: str) -> int:
    for _ in range(5):
        try:
            return session.get(f"/prices/{sku}").json()["cents"]
        except ConnectionError:
            time.sleep(1)
    raise ConnectionError(f"price lookup failed for {sku}")
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add pricing client"
