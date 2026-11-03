#!/usr/bin/env bash
set -euo pipefail
# The hook treats a folder holding .obsidian/ as the vault root, so the eval's working directory becomes one.
mkdir -p .obsidian notes
