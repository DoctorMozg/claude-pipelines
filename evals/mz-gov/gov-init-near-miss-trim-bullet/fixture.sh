#!/usr/bin/env bash
set -euo pipefail
# The governance section gov-init installed, with one bullet that runs three lines.
cat >CLAUDE.md <<'MD'
# billing-service

Python 3.12, FastAPI, Postgres. Run `make test` before every commit.

<!-- mz-gov:governance-policy v=0.62.1 start -->
# Development Governance Policy

Run `/govern <the decision>` for a change that is substantial AND ambiguous.

Exempt (no artifact needed):

- A behavior-preserving refactor.
- An objective improvement along a numeric axis, such as a speedup or a warning fix.
- A throwaway prototype or spike, meaning code written to answer a question
  quickly that we expect to delete within days and that never reaches a
  release branch, so recording its design reasoning would cost more than it saves.

An agent proposes; a human approves.
<!-- mz-gov:governance-policy end -->
MD
