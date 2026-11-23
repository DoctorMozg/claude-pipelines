#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p tests units
touch tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >textstats.py <<'PY'
def count_unique(words: list[int]) -> int:
    seen = []
    for word in words:
        if word not in seen:
            seen.append(word)
    return len(seen)
PY
cat >tests/test_textstats.py <<'PY'
import unittest

from textstats import count_unique


class CountUniqueTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(count_unique([]), 0)

    def test_repeats(self):
        self.assertEqual(count_unique([3, 1, 3, 2, 1]), 3)
PY
# Best of five in-process runs keeps the CV well under the noise ceiling.
cat >bench.py <<'PY'
import time

from textstats import count_unique

words = [i % 1500 for i in range(3000)]
best = min(
    (lambda t0: (count_unique(words), time.perf_counter() - t0)[1])(time.perf_counter())
    for _ in range(5)
)
print(f"{best * 1000:.3f}")
PY
cat >units/OP-1.md <<'MD'
# Unit OP-1: Speed up count_unique

- task: 2026_11_23_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:optimize
- owns: textstats.py
- verify: make test

## Spec

Optimize `count_unique` in `textstats.py`. Metric: wall-clock time in milliseconds, lower is better; target below 5 ms. Measurement command: `python3 bench.py`, which prints the time in ms as its only output line. Correctness command: `make test`. Cap the run at 2 iterations. Edit only `textstats.py`: `bench.py` and the tests stay as they are.
MD
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
