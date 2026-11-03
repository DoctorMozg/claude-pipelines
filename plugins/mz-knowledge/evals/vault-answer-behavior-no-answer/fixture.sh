#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up to .obsidian/.
mkdir -p .obsidian "04 - Permanent" inbox
printf '{}\n' > .obsidian/app.json

cat > CLAUDE.md <<'EOF'
# CLAUDE.md

> **Not a code repository.** This directory is an Obsidian knowledge vault. The `.md` files here are the notes themselves.

## Vault Context

- **Type**: Obsidian vault, personal engineering and cooking notes.
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

# Nothing here touches consensus protocols, so the question below has no answer in the vault.
cat > "04 - Permanent/Kafka partition keys decide ordering.md" <<'EOF'
---
created: 2026-08-03
type: permanent
tags: [kafka]
---
# Kafka partition keys decide ordering

Messages with the same key always land in the same partition, so ordering is only guaranteed per key. I pick the customer id as the key so one customer's events stay in order while the topic still spreads across all partitions.
EOF

cat > "inbox/Sourdough hydration.md" <<'EOF'
At 75% hydration my sourdough crumb is open but the dough is still easy to shape. Going up to 80% made it too slack for a free-standing loaf, so I am staying at 75% until my shaping improves.
EOF
