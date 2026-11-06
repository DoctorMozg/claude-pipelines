#!/usr/bin/env bash
set -euo pipefail
# combine finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p .mz/research .mz/reports .mz/task/2026_10_25_debug_auth_refactor

cat >.mz/research/2026_10_20_research_auth_refactor.md <<'MD'
# Auth refactor research

Session tokens move from HS256 to RS256 signing so services can verify them without the shared secret.
MD

cat >.mz/reports/2026_10_28_audit_auth_refactor.md <<'MD'
# Auth refactor audit

The refresh endpoint still accepts tokens signed with the retired HS256 key.
MD

cat >.mz/task/2026_10_25_debug_auth_refactor/state.md <<'MD'
schema_version: 2
Status: complete
Phase: done
MD

cat >.mz/task/2026_10_25_debug_auth_refactor/findings.md <<'MD'
# Findings

Logout leaves the refresh token valid for up to ten minutes.
MD

cat >.mz/reports/2025_01_10_report_billing_export.md <<'MD'
# Billing export report

The nightly export times out above 50k invoices.
MD

# The mtimes drive combine's freshness rules: the billing report is far past its 60-day limit and shares no word with the task.
touch -d '12 days ago' .mz/research/2026_10_20_research_auth_refactor.md
touch -d '5 days ago' .mz/reports/2026_10_28_audit_auth_refactor.md
touch -d '8 days ago' .mz/task/2026_10_25_debug_auth_refactor/state.md .mz/task/2026_10_25_debug_auth_refactor/findings.md
touch -d '8 days ago' .mz/task/2026_10_25_debug_auth_refactor
touch -d '400 days ago' .mz/reports/2025_01_10_report_billing_export.md
