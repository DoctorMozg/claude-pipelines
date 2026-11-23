#!/usr/bin/env bash
set -euo pipefail
# audit finds its .mz/ root and the scope with git.
git init -q
mkdir -p units
cat >cart.py <<'PY'
def total(items: list[int]) -> int:
    return sum(items[1:])


def average(items: list[int]) -> float:
    return total(items) / len(items)
PY
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
# No lens keyword and no path: interactive audit would ask which lenses to run.
cat >units/RV1-cart.md <<'MD'
# Unit RV1-cart: Check the cart before release

- task: 2026_11_23_orchestrate_eval
- kind: review
- skill: mz-dev-pipe:audit
- owns:
- verify: true

## Spec

Check the cart totals before the release goes out. Report findings with a severity of `critical`, `major` or `minor`, a `file:line` and a one-line fix; change nothing.
MD
