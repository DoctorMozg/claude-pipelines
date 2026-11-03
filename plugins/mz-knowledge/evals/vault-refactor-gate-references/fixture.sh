#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up to .obsidian/.
mkdir -p .obsidian "00 - MOCs" "04 - Permanent" "99 - Meta"
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

# The note to rename, with a heading and a block id for the heading and block link forms.
cat > "04 - Permanent/Stoicism overview.md" <<'EOF'
---
created: 2026-09-01
type: permanent
tags: [philosophy]
---
# Stoicism overview

## Ethics

Stoic ethics rests on the dichotomy of control: act on what is up to you and accept the rest. ^dichotomy
EOF

# Link forms: bare, aliased, heading, block, heading plus alias.
cat > "04 - Permanent/Dichotomy of control.md" <<'EOF'
---
created: 2026-09-05
type: permanent
tags: [philosophy]
---
# Dichotomy of control

The idea is central to [[Stoicism overview]] and comes back in [[Stoicism overview|stoa]].
See [[Stoicism overview#Ethics]] and the line at [[Stoicism overview#^dichotomy]].
Short form: [[Stoicism overview#Ethics|ethics]].
EOF

# Embed forms: note, file name with extension, heading, block.
cat > "04 - Permanent/Evening reflection routine.md" <<'EOF'
---
created: 2026-09-08
type: permanent
tags: [philosophy]
---
# Evening reflection routine

![[Stoicism overview]]

![[Stoicism overview.md]]

![[Stoicism overview#Ethics]]

![[Stoicism overview#^dichotomy]]
EOF

# Quoted wikilink in frontmatter.
cat > "00 - MOCs/Philosophy MOC.md" <<'EOF'
---
created: 2026-09-10
type: moc
related: "[[Stoicism overview]]"
tags: [moc]
---
# Philosophy MOC

Start with the overview, then follow the practices.
EOF

# Bases formulas: link() with and without a display text.
cat > "99 - Meta/Library.base" <<'EOF'
formulas:
  home: link("Stoicism overview")
  home_short: link("Stoicism overview", "stoic")
views:
  - type: table
    name: Library
    order:
      - file.name
EOF
