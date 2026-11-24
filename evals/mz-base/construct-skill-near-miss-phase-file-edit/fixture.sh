#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'plugins/mz-dev-pipe/skills/debug/phases/fix_and_verify.md')"
cat >'plugins/mz-dev-pipe/skills/debug/phases/fix_and_verify.md' <<'MD'
# Phase 4: Fix and Verify

## Step 4.1 — Apply the fix

Make the smallest change that turns the reproduction test green.

## Step 4.2 — Confirm it holds

Rerun the failing test twice; a fix that passes once and fails once is not a fix.

## Step 4.3 — Run the suite

Run the full suite and record the result in state.md.
MD
