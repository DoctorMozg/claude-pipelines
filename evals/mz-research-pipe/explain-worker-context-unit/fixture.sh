#!/usr/bin/env bash
set -euo pipefail
# explain finds its .mz/ root with git.
git init -q
mkdir -p units billing
cat >billing/invoice.py <<'PY'
from billing.discounts import apply_loyalty_discount


def invoice_total(lines: list[tuple[str, int]], years_active: int) -> int:
    subtotal = sum(price for _, price in lines)
    return apply_loyalty_discount(subtotal, years_active)
PY
cat >billing/discounts.py <<'PY'
def apply_loyalty_discount(subtotal: int, years_active: int) -> int:
    if years_active >= 5:
        return subtotal * 90 // 100
    return subtotal
PY
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
cat >units/CX1-invoice.md <<'MD'
# Unit CX1-invoice: Explain invoice totals

- task: 2026_11_23_orchestrate_eval
- kind: context
- skill: mz-research-pipe:explain
- owns:
- verify: true

## Spec

Explain how `billing/invoice.py` computes an invoice total. The units that follow change the discount rules, so say which function applies the discount, what it does and where it is called, with file:line anchors. Change nothing.
MD
