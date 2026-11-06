#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill reads the vault CLAUDE.md from the workspace root, which holds .obsidian/.
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

- Permanent notes live in `04 - Permanent/` and are titled as claims.
- Frontmatter: `created`, `type`, `tags`.
- Tags are flat: `#sleep`, `#draft`.
EOF

# About 350 words holding three separate ideas, so the proposer has to split rather than wrap one note.
cat > "inbox/sleep scribbles.md" <<'EOF'
typing while listening to the sleep episode, three things I want to keep

first one: the host said memories are not just stored overnight, they get replayed. during deep sleep the brain replays what you practiced that day and moves it from the fast temporary store into long term memory. the part that stuck with me is that the replay is tied to sleep spindles, and people who learned a task in the evening and slept on it did better the next morning than people who studied the same amount and stayed up. so cramming until three in the morning is actually the worst deal, because you buy a few more hours of study and lose the exact stage that locks it in. I should move my hardest study block to the evening and protect the sleep after it.

second thing, caffeine. the half life is around five to six hours, which means a coffee at four in the afternoon still leaves roughly a quarter of the dose in my system at bedtime. the surprising bit is that people in the study fell asleep fine but had far less deep sleep, and they did not notice it at all. they rated their sleep as normal while the measurements said otherwise. so feeling fine is not evidence that the coffee did no harm. new rule for me, last coffee before lunch, and decaf after that if I really want the ritual.

third, naps. a short nap of about twenty minutes gives a boost in alertness without dropping into deep sleep, so waking up is easy. a nap of around ninety minutes runs through a full cycle and also helps memory, but anything in between often ends in the middle of deep sleep and leaves you groggy for half an hour, which is called sleep inertia. so either set the timer for twenty minutes or commit to the full ninety, never the awkward forty five I usually do on the sofa.
EOF
