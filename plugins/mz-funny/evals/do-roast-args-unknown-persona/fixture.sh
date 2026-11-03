#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and do-roast resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p src
cat >src/billing.py <<'PY'
TAX_RATE = 0.07


def total(items):
    return sum(item["price"] * item["qty"] for item in items) * (1 + TAX_RATE)
PY
