#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >shop/pricing.py <<'EOF'
def order_total(subtotal_cents: int, discount_percent: int, shipping_cents: int) -> int:
    discount = subtotal_cents * discount_percent // 100
    return subtotal_cents - discount + shipping_cents
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
cat >units/WU-2.md <<'EOF'
# Unit WU-2: Fix discount applied to shipping

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:debug
- owns: shop/pricing.py, tests/test_pricing.py
- verify: make test

## Spec

`make test` fails in test_discount_skips_shipping: AssertionError: 1250 != 1500. The discount must apply to the subtotal only, never to shipping. Fix the bug and add a regression test.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
