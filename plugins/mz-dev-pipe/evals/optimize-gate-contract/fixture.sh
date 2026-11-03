#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p src/parser tests
touch src/__init__.py src/parser/__init__.py tests/__init__.py
cat >src/parser/tokenizer.py <<'EOF'
import re

TOKEN_RE = re.compile(r"\s*(?:(\d+)|(\w+)|(.))")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(text):
        match = TOKEN_RE.match(text, pos)
        if match is None:
            break
        tokens = tokens + [match.group().strip()]
        pos = match.end()
    return tokens
EOF
cat >bench.py <<'EOF'
import statistics
import time

from src.parser.tokenizer import tokenize

SAMPLE = "let total = price * 3 + tax(rate) ;\n" * 2000


def run_once() -> float:
    start = time.perf_counter()
    tokenize(SAMPLE)
    return (time.perf_counter() - start) * 1000


if __name__ == "__main__":
    print(f"{statistics.median(run_once() for _ in range(5)):.2f}")
EOF
cat >tests/test_tokenizer.py <<'EOF'
import unittest

from src.parser.tokenizer import tokenize


class TokenizeTests(unittest.TestCase):
    def test_splits_words_numbers_and_symbols(self):
        self.assertEqual(tokenize("x = 42;"), ["x", "=", "42", ";"])
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
