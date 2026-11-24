#!/usr/bin/env bash
set -euo pipefail
# No remote at all, so a scope:working audit must not need a base ref.
git init -q -b master
mkdir -p billing
cat >billing/__init__.py <<'EOF2'
EOF2
cat >billing/totals.py <<'EOF2'
def order_total(prices: list[int], tax_rate: float) -> int:
    """Sum prices in cents and add tax, rounded to the nearest cent."""
    subtotal = sum(prices)
    return round(subtotal * (1 + tax_rate))
EOF2
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Order totals"
# Uncommitted bug in a tracked file: the discount is applied to the tax-inclusive total and can go negative.
cat >billing/totals.py <<'EOF2'
def order_total(prices: list[int], tax_rate: float) -> int:
    """Sum prices in cents and add tax, rounded to the nearest cent."""
    subtotal = sum(prices)
    return round(subtotal * (1 + tax_rate))


def apply_coupon_zq7(total: int, coupon_cents: int) -> int:
    return total - coupon_cents
EOF2
# Untracked new file with its own bug: it divides by a caller-supplied count that can be zero.
cat >billing/split.py <<'EOF2'
def split_bill_wk4(total: int, people: int) -> int:
    return total // people
EOF2
