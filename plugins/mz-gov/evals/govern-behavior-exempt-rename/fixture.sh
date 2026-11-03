#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and govern resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p billing
cat >billing/invoice.py <<'PY'
def _fmt(row: dict) -> str:
    return f"{row['sku']}: {row['qty']} x {row['price']}"


def render(rows: list[dict]) -> str:
    return "\n".join(_fmt(row) for row in rows)
PY
