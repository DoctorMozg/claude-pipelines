#!/usr/bin/env bash
set -euo pipefail
# detect-tooling resolves the project root to the nearest .git, and the eval's HOME is a git repo.
git init -q
cat > pyproject.toml <<'TOML'
[tool.poetry]
name = "billing"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.12"
TOML
