#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >shop/pricing.py <<'EOF'
def order_total(subtotal_cents: int, discount_percent: int, shipping_cents: int) -> int:
    gross = subtotal_cents + shipping_cents
    discount = gross * discount_percent // 100
    return gross - discount
EOF
cat >tests/test_pricing.py <<'EOF'
import unittest

from shop.pricing import order_total


class OrderTotalTests(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(order_total(2000, 0, 500), 2500)

    def test_discount_skips_shipping(self):
        self.assertEqual(order_total(2000, 50, 500), 1500)
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
