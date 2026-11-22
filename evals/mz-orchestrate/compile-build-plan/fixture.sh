#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests
touch shop/__init__.py tests/__init__.py
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
printf 'PRICES = {"apple": 120, "pear": 90}\n' >shop/catalog.py
cat >plan.md <<'EOF'
# Implementation Plan: discount codes

## Summary
Checkout accepts a discount code that takes a percentage off the cart total.

## Work Units

### WU-1: Discount codes table
- **Type**: PARALLEL
- **Files**:
  - CREATE `shop/discounts.py` — `CODES = {"SPRING10": 10, "VIP25": 25}` and `percent_for(code) -> int`, 0 for an unknown code
  - CREATE `tests/test_discounts.py`
- **Changes**:
  1. Codes are matched case-insensitively.

### WU-2: Cart totals
- **Type**: PARALLEL
- **Files**:
  - CREATE `shop/cart.py` — `Cart` with `add(item, qty)` and `total() -> int` in cents, using `shop.catalog.PRICES`
  - CREATE `tests/test_cart.py`
- **Changes**:
  1. Unknown items raise `KeyError`.

### WU-3: Checkout with a code
- **Type**: SEQUENTIAL (depends on: WU-1, WU-2)
- **Files**:
  - CREATE `shop/checkout.py` — `checkout(cart, code=None) -> int`, the total after the discount, rounded down to whole cents
  - CREATE `tests/test_checkout.py`
- **Changes**:
  1. Uses `Cart.total()` and `percent_for(code)`.

## Integration Points
`shop/checkout.py` imports from `shop/cart.py` and `shop/discounts.py`.

## Test Strategy

### Unit Tests
| Test | What it verifies | Work Unit |
|------|------------------|-----------|
| test_percent_for_known_code | SPRING10 gives 10 | WU-1 |
| test_total_sums_items | 2 apples and a pear total 330 | WU-2 |
| test_checkout_applies_code | VIP25 on 330 gives 247 | WU-3 |
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
