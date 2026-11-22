#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
cat >shop/report.py <<'EOF'
import os
import sys
import json


def _old_format(rows):
    # Superseded by render(); nothing calls it any more.
    return "\n".join(str(r) for r in rows)


def render(rows: list[dict]) -> str:
    return json.dumps(rows, sort_keys=True)
EOF
cat >tests/test_report.py <<'EOF'
import unittest

from shop.report import render


class RenderTests(unittest.TestCase):
    def test_render_sorts_keys(self):
        self.assertEqual(render([{"b": 1, "a": 2}]), '[{"a": 2, "b": 1}]')
EOF
cat >units/WU-3.md <<'EOF'
# Unit WU-3: Clean up the report module

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:polish
- owns: shop/report.py
- verify: make test

## Spec

Clean up shop/report.py: remove dead code and unused imports, behavior unchanged. `make test` must stay green.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
