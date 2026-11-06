#!/usr/bin/env bash
set -euo pipefail
# detect-tooling resolves the project root to the nearest .git, and the eval's HOME is a git repo.
git init -q
cat > pyproject.toml <<'TOML'
[project]
name = "ledger"
version = "0.1.0"

[tool.ruff]
line-length = 100

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
TOML
touch uv.lock .pre-commit-config.yaml
