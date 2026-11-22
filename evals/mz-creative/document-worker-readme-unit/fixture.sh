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
    """Return the order total in cents; the discount applies to the subtotal only."""
    if not 0 <= discount_percent <= 100:
        raise ValueError(f"discount_percent must be 0-100, got {discount_percent}")
    discount = subtotal_cents * discount_percent // 100
    return subtotal_cents - discount + shipping_cents
EOF
cat >units/WU-5.md <<'EOF'
# Unit WU-5: README for the shop package

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-creative:document
- owns: README.md
- verify: test -s README.md

## Spec

Write a short README.md at the repository root for the `shop` package: what `order_total` computes, its arguments in cents and percent, the ValueError it raises, one usage example, and how to run the tests (`make test`).
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
