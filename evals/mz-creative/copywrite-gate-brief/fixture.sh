#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and copywrite resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

cat >brief.md <<'MD'
# Ledgerline CSV export v2

Product: Ledgerline, bookkeeping software for subscription businesses.
Feature: the CSV export now streams, so a 12-month ledger exports in 4 seconds instead of 90.
Audience: finance operations managers at companies with 20 or more subscription plans.
Value claim: month-end close no longer waits on the export.
Evidence: Bramble & Co cut their close from 3 days to 2 after switching on streaming export (their words, used with permission).
Launch date: 2026-11-10.
CTA: https://example.invalid/ledgerline/export
Tone: plain, no hype. Banned words: revolutionary, seamless.
MD
