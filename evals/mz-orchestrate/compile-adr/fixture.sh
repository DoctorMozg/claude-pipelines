#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p api tests docs/adr
touch api/__init__.py tests/__init__.py
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >api/handlers.py <<'EOF'
def handle(client_id: str, path: str) -> tuple[int, str]:
    return 200, f"ok {path}"
EOF
cat >docs/adr/0007-rate-limiting.md <<'EOF'
---
status: "accepted"
date: 2026-11-20
deciders: platform team
---

# Rate-limit API clients with an in-process token bucket

## Context and Problem Statement

One client can flood `api.handlers.handle`. We need a per-client limit.

## Decision Drivers

- No new infrastructure.
- Limits must be testable without sleeping.

## Considered Options

- Token bucket in process
- Redis-backed counter

## Decision Outcome

Chosen option: "Token bucket in process", because it needs no new infrastructure.

- `api/ratelimit.py` holds a `TokenBucket(capacity, refill_per_sec, clock)` with `allow() -> bool`; the clock is injected so tests control time.
- `api/handlers.handle` keeps one bucket per `client_id` (capacity 5, refill 1 per second) and returns `(429, "slow down")` when `allow()` is false.

### Consequences

- Good, because there is nothing new to run.
- Bad, because limits reset when the process restarts.

## More Information

Redis was rejected; don't add it.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
