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

- **Type**: Obsidian vault, personal study notes.
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

# No time units or intervals anywhere, so any duration in the answer can only come from general knowledge.
cat > "04 - Permanent/Retrieval practice beat rereading.md" <<'EOF'
---
created: 2026-09-14
type: permanent
tags: [learning]
---
# Retrieval practice beat rereading

In my own flashcard log from August and September, the 120 cards I quizzed myself on were still remembered at 82% at my final check. The 120 cards I only reread were remembered at 54%. Rereading felt easier and more productive while I did it, but the recall numbers say the effort of retrieving the answer is what made the difference.
EOF

cat > "04 - Permanent/Spaced repetition widens the gaps between reviews.md" <<'EOF'
---
created: 2026-09-20
type: permanent
tags: [learning]
---
# Spaced repetition widens the gaps between reviews

Spaced repetition schedules each review just before the memory would fade, so the gap grows after every successful recall. In my Anki decks the cards that survive their first few reviews tend to stay known for a very long time, which is why most of my daily effort goes to the newest cards.
EOF

cat > "inbox/Sourdough hydration.md" <<'EOF'
At 75% hydration my sourdough crumb is open but the dough is still easy to shape. Going up to 80% made it too slack for a free-standing loaf, so I am staying at 75% until my shaping improves.
EOF
