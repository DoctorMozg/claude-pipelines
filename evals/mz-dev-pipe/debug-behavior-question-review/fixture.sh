#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
# A half-up rounding helper exists; the fix can use it or round inline, which gives the questioner a choice to ask about.
cat >shop/money.py <<'EOF'
from decimal import ROUND_HALF_UP, Decimal


def round_cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
EOF
cat >shop/tax.py <<'EOF'
def tax_cents(subtotal_cents: int, rate_percent: int) -> int:
    return round(subtotal_cents * rate_percent / 100)
EOF
cat >tests/test_tax.py <<'EOF'
import unittest

from shop.tax import tax_cents


class TaxTests(unittest.TestCase):
    def test_whole_cents(self):
        self.assertEqual(tax_cents(1000, 20), 200)

    def test_half_cent_rounds_up(self):
        self.assertEqual(tax_cents(250, 1), 3)
EOF
cat >units/WU-2.md <<'EOF'
# Unit WU-2: Fix tax rounding on half cents

- task: 2026_11_24_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:debug
- owns: shop/tax.py, tests/test_tax.py
- verify: make test

## Spec

`make test` fails in test_half_cent_rounds_up: AssertionError: 2 != 3. Tax must round half a cent up, as the rest of the shop does, but tax_cents(250, 1) returns 2. Fix the bug and add a regression test.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
