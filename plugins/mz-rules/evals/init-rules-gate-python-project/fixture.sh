#!/usr/bin/env bash
set -euo pipefail
# init-rules finds its .mz/ root and detects the stack with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p invoice_tool
cat >pyproject.toml <<'TOML'
[project]
name = "invoice-tool"
version = "0.1.0"
requires-python = ">=3.11"
TOML

cat >.pre-commit-config.yaml <<'YAML'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
YAML

cat >invoice_tool/core.py <<'PY'
def total(items: list[float]) -> float:
    return sum(items)
PY
