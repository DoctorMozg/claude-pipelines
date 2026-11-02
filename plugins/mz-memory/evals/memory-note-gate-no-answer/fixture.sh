#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-10-01] Use UTC timestamps everywhere." ""
