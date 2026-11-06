#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and brainstorm resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
