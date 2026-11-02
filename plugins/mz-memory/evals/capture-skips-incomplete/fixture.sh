#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "" ""
write_task 2026_11_01_build_export_csv complete <<'STATE'
## Decisions
- Stream CSV rows instead of buffering the whole export
STATE
write_task 2026_11_02_debug_flaky_upload in_progress <<'STATE'
## Decisions
- Switch uploads to multipart

## Lessons
- Retry uploads only on 5xx responses, never on 4xx
STATE
