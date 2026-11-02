#!/usr/bin/env bash
set -euo pipefail
# detect-tooling resolves the project root to the nearest .git, and the eval's HOME is a git repo.
git init -q
printf 'module example.com/svc\n\ngo 1.23\n' > go.mod
printf '[package]\nname = "core"\nversion = "0.1.0"\n' > Cargo.toml
printf '{"name": "ui", "private": true}\n' > package.json
