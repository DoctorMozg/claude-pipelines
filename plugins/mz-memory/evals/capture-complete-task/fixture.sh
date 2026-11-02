#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "" ""
write_task 2026_11_02_build_password_reset complete <<'STATE'
## Decisions
- Hash reset tokens with argon2id <private>pepper=hunter2</private> before storing them

## Notes
- Reset links expire after 20 minutes

## Lessons
- Seed fixtures before running migrations in tests
STATE
