#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p tests
touch tests/__init__.py
cat >calc.py <<'EOF'
import os


def average(values):
    if not values:
        return 0
    return sum(values) // len(values)


def clamp(value, low, high):
    return max(low, min(value, high))
EOF
cat >tests/test_calc.py <<'EOF'
import unittest

from calc import average, clamp


class AverageTests(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(average([]), 0)

    def test_fractional_mean(self):
        self.assertEqual(average([1, 2]), 1.5)


class ClampTests(unittest.TestCase):
    def test_inside_range(self):
        self.assertEqual(clamp(5, 0, 10), 5)
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
