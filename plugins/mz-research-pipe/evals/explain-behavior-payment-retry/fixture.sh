#!/usr/bin/env bash
set -euo pipefail
# explain finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p src/payments
touch src/payments/__init__.py

cat >src/payments/errors.py <<'PY'
class PaymentError(Exception):
    """Base class for payment failures."""


class TransientError(PaymentError):
    """The gateway is temporarily unavailable; repeating the call is safe."""


class PaymentFailed(PaymentError):
    """The charge was not completed after every attempt."""
PY

cat >src/payments/retry.py <<'PY'
import logging
import random
import time
from typing import Callable, TypeVar

from .errors import PaymentFailed, TransientError

log = logging.getLogger(__name__)

T = TypeVar("T")

MAX_ATTEMPTS = 4
BASE_DELAY = 0.25
JITTER = 0.1


def retry_with_backoff(call: Callable[[], T]) -> T:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except TransientError as exc:
            if attempt == MAX_ATTEMPTS:
                raise PaymentFailed(f"gave up after {attempt} attempts") from exc
            delay = BASE_DELAY * 2 ** (attempt - 1) + random.uniform(0, JITTER)
            log.warning("attempt %d failed, retrying in %.2fs", attempt, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")
PY

cat >src/payments/gateway.py <<'PY'
from .errors import PaymentError, TransientError


class Gateway:
    """In-memory stand-in for the card processor; every third call times out."""

    def __init__(self) -> None:
        self._calls = 0

    def charge(self, order_id: str, amount_cents: int) -> str:
        if amount_cents <= 0:
            raise PaymentError(f"invalid amount for {order_id}: {amount_cents}")
        self._calls += 1
        if self._calls % 3 == 0:
            raise TransientError("gateway timeout")
        return f"txn-{order_id}-{self._calls}"
PY

cat >src/payments/processor.py <<'PY'
import logging
from dataclasses import dataclass

from .gateway import Gateway
from .retry import retry_with_backoff

log = logging.getLogger(__name__)


@dataclass
class Order:
    order_id: str
    amount_cents: int


def process_payment(order: Order, gateway: Gateway) -> str:
    txn = retry_with_backoff(lambda: gateway.charge(order.order_id, order.amount_cents))
    log.info("order %s charged: %s", order.order_id, txn)
    return txn
PY
