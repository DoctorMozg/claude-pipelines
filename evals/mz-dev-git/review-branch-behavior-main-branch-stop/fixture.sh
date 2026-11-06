#!/usr/bin/env bash
set -euo pipefail
# review-branch reads the current branch and finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q -b main
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

cat >README.md <<'MD'
# demo

A tiny service used by the review-branch eval.
MD
git add README.md
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add readme"
