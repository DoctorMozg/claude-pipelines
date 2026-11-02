#!/usr/bin/env bash
set -euo pipefail

# Appends a pre-formatted markdown block to the interaction journal
# (.mz/journal.md) under an flock, redacting <private> regions.
# Used by journal-capture.sh. Skills append directly with `>>`.
#
# Usage: printf '%s' "$block" | journal-append.sh
#        journal-append.sh "block text"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT_DIR=$(find_project_root)
JOURNAL_FILE="${PROJECT_DIR}/.mz/journal.md"

if [[ -n "${1:-}" ]]; then
  printf '%s' "$1" | journal_append "$JOURNAL_FILE"
else
  journal_append "$JOURNAL_FILE"
fi
