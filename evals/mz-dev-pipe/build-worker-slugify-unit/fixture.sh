#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >units/WU-4.md <<'EOF'
# Unit WU-4: Add slugify helper

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:build
- owns: shop/text.py, tests/test_text.py
- verify: make test

## Spec

Add `slugify(text: str) -> str` in shop/text.py: lowercase the text, replace every run of characters other than ASCII letters and digits with one hyphen, and strip hyphens from both ends. `slugify("  Hello, World!  ")` returns `"hello-world"`, and an empty or all-punctuation string returns `""`. Cover it with unittest tests in tests/test_text.py.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
