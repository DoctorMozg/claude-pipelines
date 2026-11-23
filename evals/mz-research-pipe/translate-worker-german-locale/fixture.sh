#!/usr/bin/env bash
set -euo pipefail
# The workspace may already be a repository; init is harmless there and needed when HOME is the only repo.
git init -q
mkdir -p locales/en units
cat >locales/en/app.json <<'JSON'
{
  "greeting": "Welcome back, {name}!",
  "save": "Save changes",
  "cancel": "Cancel",
  "logout": "Sign out"
}
JSON
cat >units/TR-de.md <<'EOF2'
# Unit TR-de: Localize the app strings into German

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-research-pipe:translate
- owns: locales/de/**
- verify: python3 -c "import json; json.load(open('locales/de/app.json'))"

## Spec

Translate `locales/en/app.json` into German with `mode:i18n`, so the result lands in `locales/de/app.json`. Keep the `{name}` placeholder exactly as written. Glossary: "Welcome" is "Willkommen", and use the informal "du" register. Do not touch the English file.
EOF2
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
