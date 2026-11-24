#!/usr/bin/env bash
set -euo pipefail
# main has a retry helper already in use; the feature branch adds a client that hand-rolls its own retry loop.
git init -q -b main
mkdir -p src/util src/billing
touch src/__init__.py src/util/__init__.py src/billing/__init__.py

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

cat >src/billing/client.py <<'PY'
from src.util.retry import retry_with_backoff


class BillingClient:
    def __init__(self, transport):
        self._transport = transport

    def invoice(self, invoice_id):
        return retry_with_backoff(lambda: self._transport.get(f"/invoices/{invoice_id}"))
PY

cat >README.md <<'MD'
# shop

Service clients. Network calls go through `src/util/retry.py`.
MD
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
# The workspace may already be a repository, where init's -b is ignored, so name the branch explicitly.
git branch -M main

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
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add inventory client"
