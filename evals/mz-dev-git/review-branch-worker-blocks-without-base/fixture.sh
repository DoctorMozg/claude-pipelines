#!/usr/bin/env bash
set -euo pipefail
# review-branch finds its .mz/ root and the diff with git.
git init -q -b main
mkdir -p units
printf 'def total(items):\n    return sum(items)\n' >cart.py
git add -A
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m init
# The workspace may already be a repository, where init's -b is ignored, so name the branch explicitly.
git branch -M main
git checkout -q -b orch-eval-FR1-app
printf 'def total(items):\n    return sum(items[1:])\n' >cart.py
git -c user.name=eval -c user.email=eval@example.invalid commit -q -am "Change total"
# The brief names no base branch, so the worker can't know what to diff against.
cat >units/FR1-app.md <<'MD'
# Unit FR1-app: Final review of app

- task: 2026_11_23_orchestrate_eval
- kind: review
- skill: mz-dev-git:review-branch
- owns:
- verify: true

## Spec

Review every change the run made on this branch. Report findings with a severity of `critical`, `major` or `minor`, a `file:line` and a one-line fix; change nothing.
MD
