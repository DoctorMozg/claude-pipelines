#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill is given the vault path as an argument, and the workspace root holds .obsidian/.
mkdir -p .obsidian "04 - Permanent"
printf '{}\n' > .obsidian/app.json

cat > CLAUDE.md <<'EOF'
# CLAUDE.md

> **Not a code repository.** This directory is an Obsidian knowledge vault. The `.md` files here are the notes themselves.

## Vault Context

- **Type**: Obsidian vault, personal engineering notes.
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

# The hub and the leaf link to each other, so neither is an orphan; the hub also links to a note that does not exist.
cat > "04 - Permanent/Linked hub.md" <<'EOF'
---
created: 2026-10-01
type: permanent
tags: [graphs]
---
# Linked hub

Everything about how the leaf note fits in lives in [[Linked leaf]]. I still owe a note on [[Ghost note]], which I keep meaning to write.
EOF

cat > "04 - Permanent/Linked leaf.md" <<'EOF'
---
created: 2026-10-02
type: permanent
tags: [graphs]
---
# Linked leaf

This note hangs off [[Linked hub]] and shares the same topic of connected notes.
EOF

# Nothing links to it and it links to nothing.
cat > "04 - Permanent/Lonely orphan.md" <<'EOF'
---
created: 2026-10-03
type: permanent
tags: [graphs]
---
# Lonely orphan

A note that nobody points to and that points nowhere, so the graph view shows it as a dot with no edges at all.
EOF
