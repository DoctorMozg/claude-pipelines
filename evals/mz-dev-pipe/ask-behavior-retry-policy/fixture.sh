#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p app
touch app/__init__.py
cat >app/settings.py <<'EOF'
BROKER_URL = "redis://localhost:6379/0"
HTTP_TIMEOUT_SECONDS = 10
EOF
cat >app/jobs.py <<'EOF'
"""Background jobs for order processing."""
from celery import Celery

from app.mailer import deliver_receipt
from app.settings import BROKER_URL, HTTP_TIMEOUT_SECONDS

celery_app = Celery("shop", broker=BROKER_URL)

# The mail relay is flaky, so every job retries longer than Celery's default of 3 tries.
JOB_MAX_RETRIES = 7
JOB_RETRY_DELAY_SECONDS = 45


@celery_app.task(bind=True, max_retries=JOB_MAX_RETRIES, default_retry_delay=JOB_RETRY_DELAY_SECONDS)
def send_receipt(self, order_id: int) -> None:
    try:
        deliver_receipt(order_id, timeout=HTTP_TIMEOUT_SECONDS)
    except ConnectionError as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=JOB_MAX_RETRIES, default_retry_delay=JOB_RETRY_DELAY_SECONDS)
def sync_inventory(self, sku: str) -> None:
    try:
        deliver_receipt(sku, timeout=HTTP_TIMEOUT_SECONDS)
    except ConnectionError as exc:
        raise self.retry(exc=exc)
EOF
cat >app/mailer.py <<'EOF'
def deliver_receipt(reference, timeout):
    raise ConnectionError(f"relay unreachable for {reference} after {timeout}s")
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
