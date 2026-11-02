#!/usr/bin/env bash
set -euo pipefail
# /naturalize finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
cat >retries.md <<'EOF'
# Configuring Retries

The client library provides a robust and seamless retry mechanism that empowers you to handle transient failures with ease. In this guide, we'll delve into the two settings that matter — `max_retries` and `backoff_ms` — and explain how they interact.

## Defaults

By default, the client retries 3 times with an initial backoff of 250 ms; each subsequent attempt doubles the wait. This means a request can take up to 1.75 seconds before it finally fails.

## Changing the settings

```python
client = Client(max_retries=5, backoff_ms=100)
```

It's important to note that retries only apply to idempotent requests (GET, PUT, DELETE). POST requests are never retried automatically → you must opt in with `retry_unsafe=True`.

## When to adjust

If your service sits behind a load balancer with a 2-second timeout, keep the total retry budget below that limit… otherwise the balancer will cut the connection first. Version 2.7.0 added a `max_elapsed_ms` cap for exactly this reason.
EOF
