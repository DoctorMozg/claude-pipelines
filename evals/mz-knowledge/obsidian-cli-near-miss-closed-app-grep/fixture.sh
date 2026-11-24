#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'notes/Q3 billing.md')"
cat >'notes/Q3 billing.md' <<'MD'
Sent the invoice to Acme on Monday.
MD
mkdir -p "$(dirname 'notes/Freelance.md')"
cat >'notes/Freelance.md' <<'MD'
Every invoice goes out on the 1st; a late invoice gets a reminder.
MD
mkdir -p "$(dirname 'notes/Taxes 2026.md')"
cat >'notes/Taxes 2026.md' <<'MD'
Keep each invoice PDF for seven years.
MD
mkdir -p "$(dirname 'notes/Reading list.md')"
cat >'notes/Reading list.md' <<'MD'
Thinking, Fast and Slow.
MD
mkdir -p "$(dirname 'notes/Garden.md')"
cat >'notes/Garden.md' <<'MD'
Tomatoes need staking by June.
MD
