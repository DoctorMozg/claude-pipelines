#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and gov-init resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

cat >CLAUDE.md <<'MD'
# Acme Billing house rules

- Run `make test` before every push.
- Money is stored as integer cents.
MD
