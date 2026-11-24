#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname 'Reading/Show Your Work.md')"
cat >'Reading/Show Your Work.md' <<'MD'
---
status: evergreen
author: Austin Kleon
tags: [book, creativity]
---
# Show Your Work

## Takeaways

- Share the process, not only the finished piece.
- The book came out in 2019 and reads in an afternoon.
MD
