#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib/fixture.sh"
init_project
write_memory "- [2026-09-03] This repo uses pnpm exclusively; npm and yarn lockfiles are rejected in CI." ""
