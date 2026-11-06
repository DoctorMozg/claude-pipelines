#!/usr/bin/env bash
set -euo pipefail
# Eval workspaces aren't git repositories, and document resolves .mz/ through git.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p src/pluginbox

cat >pyproject.toml <<'TOML'
[project]
name = "pluginbox"
version = "0.3.1"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]
TOML

cat >README.md <<'MD'
# pluginbox

A tiny plugin loader.
MD

cat >src/pluginbox/__init__.py <<'PY'
from .loader import ManifestError, discover_manifests, load_hooks

__all__ = ["ManifestError", "discover_manifests", "load_hooks"]
PY

cat >src/pluginbox/loader.py <<'PY'
from pathlib import Path

import yaml


class ManifestError(Exception):
    """Raised when a plugin.yaml has no name."""


def discover_manifests(root: Path) -> list[dict]:
    manifests = []
    for path in sorted(root.glob("*/plugin.yaml")):
        data = yaml.safe_load(path.read_text())
        if "name" not in data:
            raise ManifestError(f"{path} has no name")
        manifests.append(data)
    return manifests


def load_hooks(manifest: dict) -> list[str]:
    return manifest.get("hooks", [])
PY
