#!/usr/bin/env bash
set -euo pipefail
# translate finds its .mz/ root with git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init

mkdir -p docs
cat >docs/guide.md <<'MD'
# Getting started

Hello, {{user.name}}! You have %d unread messages.

## Install

```bash
pip install invoice-tool
```
MD
