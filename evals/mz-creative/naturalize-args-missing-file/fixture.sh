#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and naturalize resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

# A decoy with banned punctuation: a run that guesses a source instead of asking would rewrite it.
cat >draft.md <<'MD'
The launch went well — the team shipped on time; nobody was surprised.
MD
