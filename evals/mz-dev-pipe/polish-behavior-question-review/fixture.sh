#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p shop tests units
touch shop/__init__.py tests/__init__.py
# The Makefile is how the tooling detector finds a test command: eval sessions load no CLAUDE.md.
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
# A logic fix, not a typo, so polish sends it through the Phase 4 fix loop and its code review.
cat >shop/tags.py <<'EOF'
def unique_tags(tags: list[str]) -> list[str]:
    return list(set(tag.strip().lower() for tag in tags))
EOF
cat >tests/test_tags.py <<'EOF'
import unittest

from shop.tags import unique_tags


class UniqueTagsTests(unittest.TestCase):
    def test_keeps_first_seen_order(self):
        self.assertEqual(unique_tags(["Sale", "new", "sale", " New ", "gift"]), ["sale", "new", "gift"])

    def test_drops_blank_tags(self):
        self.assertEqual(unique_tags(["", "  ", "gift"]), ["gift"])
EOF
cat >units/WU-5.md <<'EOF'
# Unit WU-5: Make the tag tests pass

- task: 2026_11_24_orchestrate_eval
- kind: change
- skill: mz-dev-pipe:polish
- owns: shop/tags.py
- verify: make test

## Spec

`make test` must pass. Both tests in tests/test_tags.py fail: unique_tags loses the first-seen order of tags and keeps blank ones. Fix shop/tags.py; the tests are correct and stay as they are.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
