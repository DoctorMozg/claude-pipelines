#!/usr/bin/env bash
set -euo pipefail
# deep-research finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
