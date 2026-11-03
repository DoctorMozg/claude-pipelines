#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up to .obsidian/.
mkdir -p .obsidian "04 - Permanent"
printf '{}\n' > .obsidian/app.json

cat > CLAUDE.md <<'EOF'
# CLAUDE.md

> **Not a code repository.** This directory is an Obsidian knowledge vault. The `.md` files here are the notes themselves.

## Vault Context

- **Type**: Obsidian vault, personal philosophy notes.
- **Mozg pipelines**: `.mz/` is active.

## Folder Layout

```text
00 - MOCs/
01 - Projects/
02 - Areas/
03 - Resources/
04 - Permanent/
inbox/
daily/
07 - Archives/
99 - Meta/
```

## Note Conventions

- Permanent notes are titled as claims.
- Frontmatter: `created`, `type`, `tags`.
EOF

cat > "04 - Permanent/Stoicism overview.md" <<'EOF'
---
created: 2026-09-01
type: permanent
tags: [philosophy]
---
# Stoicism overview

Stoic ethics rests on the dichotomy of control: act on what is up to you and accept the rest.
EOF

cat > "04 - Permanent/Dichotomy of control.md" <<'EOF'
---
created: 2026-09-05
type: permanent
tags: [philosophy]
---
# Dichotomy of control

The idea is central to [[Stoicism overview]].
EOF
