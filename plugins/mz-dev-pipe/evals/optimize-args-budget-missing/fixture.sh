#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p src/parser
touch src/__init__.py src/parser/__init__.py
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
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
