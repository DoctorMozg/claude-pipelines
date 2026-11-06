#!/usr/bin/env bash
set -euo pipefail
# The workspace isn't a repo and HOME is, so without this the skill's .mz/ root resolves to HOME.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
