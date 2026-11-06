#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up to .obsidian/.
mkdir -p .obsidian "04 - Permanent" inbox
printf '{}\n' > .obsidian/app.json

# The scorer reads each note's age from created:, so the dates are computed from today.
today=$(date +%F)
sixty_days_ago=$(date -d '60 days ago' +%F 2>/dev/null || date -v-60d +%F)

# The skill reads the permanent folder from here and never falls back to a guess.
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
04 - Permanent/    # evergreen atomic notes
inbox/             # raw captures, promote or discard within days
daily/
07 - Archives/
99 - Meta/
```

## Note Conventions

- Permanent notes are titled as claims.
- Frontmatter: `created`, `type`, `tags`.
EOF

cat > "04 - Permanent/Kafka partition keys decide ordering.md" <<'EOF'
---
created: 2026-08-03
type: permanent
tags: [kafka]
---
# Kafka partition keys decide ordering

Messages with the same key always land in the same partition, so ordering is only guaranteed per key.
EOF

# Under 20 words with no links: the first ladder rule discards it.
cat > "inbox/Lunch idea.md" <<'EOF'
Try the new noodle place on Friday.
EOF

# 100+ words, one link and a status: the structured-note rule promotes it.
cat > "inbox/Postgres vacuum notes.md" <<EOF
---
created: $today
status: draft
---
Autovacuum keeps table bloat in check, but its defaults are tuned for small tables and fall behind on big ones. On the orders table the dead tuples piled up faster than the worker could clear them, because the scale factor waited until a fifth of the rows were dead before starting a run. Lowering the scale factor for that one table made vacuum start earlier and finish faster, and the bloat stopped growing. Next I want to compare this with a fixed threshold instead of a ratio, and check whether the cost limit also needs raising. The background reading is in [[Postgres]] and I should write up the settings once the numbers settle.
EOF

# 20 to 99 words, no links, created 60 days ago: the stale-stub rule discards it.
cat > "inbox/Old reading list.md" <<EOF
---
created: $sixty_days_ago
---
Books to look at when the project calms down: something on distributed systems, one good book on writing clearly, and a history of the typewriter that a friend recommended last spring. None of them is urgent, I just do not want to forget the titles.
EOF

# 50+ words, no links, created today: the fresh-note rule defers it.
cat > "inbox/Standup ideas.md" <<EOF
---
created: $today
---
Ideas for making the daily standup shorter: each person says only what is blocked, anything that needs a discussion moves to a separate thread after the meeting, and the notes go into the channel afterwards so absent teammates can catch up. Maybe try it for two weeks and see whether the team still feels informed.
EOF
