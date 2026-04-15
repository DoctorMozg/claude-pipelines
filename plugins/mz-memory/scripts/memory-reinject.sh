#!/usr/bin/env bash
set -euo pipefail

# PostCompact hook — re-injects memory after context compaction.
# Sources the shared inject_memory() function from memory-inject.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=memory-inject.sh
source "${SCRIPT_DIR}/memory-inject.sh" 2>/dev/null || true

inject_memory "PostCompact" "[PostCompact] Project memory" || exit 0

exit 0
