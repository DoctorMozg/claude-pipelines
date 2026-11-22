#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p notes tests
touch notes/__init__.py tests/__init__.py
printf 'test:\n\tpython3 -m unittest discover -s tests -t .\n' >Makefile
printf '# notes\n\nA tiny note-taking package.\n' >README.md
cat >PLAN.md <<'EOF'
# Plan: tags for notes

We agreed on this in review; it is final. Run the Docs step on Codex; everything else stays on Claude.

1. Storage: add `notes/store.py` with a `Note` dataclass (`id: int`, `text: str`, `tags: set[str]`) and a `NoteStore` that keeps notes in memory and supports `add(text, tags)`, `get(id)` and `by_tag(tag)`. Tags are lowercased on the way in.
2. Search: add `notes/search.py` with `search(store, query)` that matches text case-insensitively and a `#tag` token as a tag filter. It uses `NoteStore.by_tag`.
3. Export: add `notes/export.py` with `to_markdown(notes)` that renders one bullet per note with its tags in backticks. It needs only the `Note` dataclass.
4. Docs: a "Tags" section in README.md showing add, search and export.

Every module gets unittest tests under tests/. No third-party dependencies.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
