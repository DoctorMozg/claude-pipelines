#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and govern resolves .mz/ through git.
git init -q

mkdir -p webhooks docs/decisions
cat >README.md <<'MD'
# shopbridge

Receives order webhooks from two payment providers and turns them into ledger entries.
MD
cat >webhooks/signing.py <<'PY'
import hashlib
import hmac


def valid_signature(secret: bytes, body: bytes, header: str) -> bool:
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
PY
cat >webhooks/handlers.py <<'PY'
from webhooks.signing import valid_signature

SECRETS = {"stripe": b"s-secret", "adyen": b"a-secret"}


def stripe_order(body: bytes, headers: dict) -> int:
    if not valid_signature(SECRETS["stripe"], body, headers.get("Stripe-Signature", "")):
        return 401
    return 200


def adyen_order(body: bytes, headers: dict) -> int:
    # Adyen retries for 24 hours, so a rejected call comes back.
    if not valid_signature(SECRETS["adyen"], body, headers.get("Hmac-Signature", "")):
        return 401
    return 200
PY
cat >webhooks/app.py <<'PY'
from webhooks.handlers import adyen_order, stripe_order

ROUTES = {"/hooks/stripe": stripe_order, "/hooks/adyen": adyen_order}


def dispatch(path: str, body: bytes, headers: dict) -> int:
    handler = ROUTES.get(path)
    return handler(body, headers) if handler else 404
PY
cat >docs/decisions/0001-hmac-sha256-signatures.md <<'MD'
# 1. Verify webhooks with HMAC-SHA256

Status: accepted

## Context
Both providers sign the raw body with a shared secret.

## Decision
Verify every webhook with HMAC-SHA256 and a constant-time compare.

## Consequences
Each provider's secret lives in SECRETS until we move secrets to the vault.
MD
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
