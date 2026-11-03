#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up to .obsidian/.
mkdir -p .obsidian .mz "04 - Permanent" inbox
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

# Only the permanent type is declared, so recipe notes and untyped notes are pass-through.
cat > .mz/vault-schema.yml <<'EOF'
conventions:
  tag_case: keep
  key_order: schema

note_types:
  permanent:
    required: [created, type, tags]
    optional: [updated, source, last_reviewed, status]
    allowed_values:
      status: [draft, evergreen]
EOF

# Lacks the required tags key.
cat > "04 - Permanent/Cache invalidation.md" <<'EOF'
---
created: 2026-10-01
type: permanent
---
# Cache invalidation

A cache entry is only as fresh as the event that last invalidated it, so I tie invalidation to writes instead of timers.
EOF

# status is outside the declared draft or evergreen values.
cat > "04 - Permanent/Merge sort.md" <<'EOF'
---
created: 2026-10-02
type: permanent
tags: [algorithms]
status: wip
---
# Merge sort

Merge sort splits the input in halves, sorts each half and merges the results, which keeps it at n log n in every case.
EOF

# mood is neither required nor optional.
cat > "04 - Permanent/Binary search.md" <<'EOF'
---
created: 2026-10-03
type: permanent
tags: [algorithms]
mood: curious
---
# Binary search

Binary search halves the remaining range on every probe, so a sorted list of a million items needs about twenty probes.
EOF

cat > "04 - Permanent/Clean note.md" <<'EOF'
---
created: 2026-10-04
type: permanent
tags: [writing]
status: draft
---
# Clean note

This note satisfies every rule of the permanent type.
EOF

# No type key, so the validator skips it.
cat > "inbox/Untyped scribble.md" <<'EOF'
---
created: 2026-10-05
tags: [misc]
---
Buy more index cards before the weekend.
EOF

# A type the schema does not declare, so the validator skips it.
cat > "04 - Permanent/Pasta recipe.md" <<'EOF'
---
created: 2026-10-06
type: recipe
tags: [cooking]
---
# Pasta recipe

Salt the water until it tastes like the sea and pull the pasta a minute early.
EOF
