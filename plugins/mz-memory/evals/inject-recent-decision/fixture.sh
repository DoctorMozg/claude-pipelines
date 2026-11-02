#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "" "- [2026-10-28] 2026_10_28_build_session_tokens (phase=done) [main@4f2a9c1]
  - Access tokens expire after 15 minutes; refresh tokens after 30 days.
- [2026-10-21] 2026_10_21_build_audit_log (phase=done) [main@81be3d0]"
