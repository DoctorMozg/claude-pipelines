#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repository but its HOME is, so .mz/ and git ls-files would resolve to HOME without this.
git init -q
mkdir -p docs/release-notes units
cat >CHANGELOG.md <<'EOF'
# Changelog

## 2.0.0

- Added `ledgerline export --format csv`, which writes one row per posted transaction.
- The CSV export streams, so a 1 million row ledger uses under 50 MB of memory.
- Removed the deprecated `--legacy-json` flag.

## 1.9.0

- Added `ledgerline reconcile`, which matches bank lines to ledger entries.

## 1.8.2

- Fixed a crash when a transaction memo contained a tab character.
EOF
cat >units/WU-4.md <<'EOF'
# Unit WU-4: Release notes for v2.0.0

- task: 2026_11_22_orchestrate_eval
- kind: change
- skill: mz-creative:copywrite
- owns: docs/release-notes/v2.md
- verify: test -s docs/release-notes/v2.md

## Spec

Write the v2.0.0 release notes for Ledgerline, format:changelog, into docs/release-notes/v2.md. Audience: accountants and developers who run the Ledgerline CLI. Goal: they know what changed and whether they must act. Product facts, the only ones to use: `ledgerline export --format csv` writes one row per posted transaction; the export streams, so a 1 million row ledger needs under 50 MB of memory; the `--legacy-json` flag is removed, so scripts that pass it must stop. Tone: plain and brief, no hype.
EOF
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m fixture
