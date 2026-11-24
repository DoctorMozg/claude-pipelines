#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
# The repo already has a retry helper; the spec doesn't mention it, so a hand-rolled loop is the choice to question.
cat >shop/retry.py <<'EOF'
import time


def retry(fn, attempts, exceptions, delay=0.0):
    """Call fn until it succeeds, at most `attempts` times, re-raising the last error."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except exceptions:
            if attempt == attempts:
                raise
            time.sleep(delay)
EOF
cat >units/WU-7.md <<'EOF'
# Unit WU-7: Fetch exchange rates with retries

- task: 2026_11_24_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:build
- owns: shop/rates.py, tests/test_rates.py
- verify: make test

## Spec

Add `fetch_rates(source) -> dict` in shop/rates.py. It calls `source()` and returns the dict it gives back. When `source()` raises ConnectionError, call it again, up to 3 calls in total; after the third failure, raise that last ConnectionError. Any other exception propagates at once. Cover it with unittest tests in tests/test_rates.py.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
