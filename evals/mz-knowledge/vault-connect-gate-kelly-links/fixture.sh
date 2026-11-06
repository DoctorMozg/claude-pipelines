#!/usr/bin/env bash
set -euo pipefail
# The skill finds .mz/ through git, and the eval workspace isn't a repository.
git init -q
git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
# The skill finds the vault by walking up from the target note to .obsidian/.
mkdir -p .obsidian "04 - Permanent" inbox
printf '{}\n' > .obsidian/app.json

cat > CLAUDE.md <<'EOF'
# CLAUDE.md

> **Not a code repository.** This directory is an Obsidian knowledge vault. The `.md` files here are the notes themselves.

## Vault Context

- **Type**: Obsidian vault, personal notes on investing, engineering and cooking.
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
- Link a concept that has its own note with a `[[wikilink]]`.
EOF

# No note links to any other yet, so any [[ in the vault after the run was written by the skill.
cat > "04 - Permanent/Kelly criterion.md" <<'EOF'
---
created: 2026-10-02
type: permanent
tags: [investing]
---
# Kelly criterion

The Kelly criterion sizes a repeated bet so that long-run bankroll growth is maximal: stake the fraction of the bankroll equal to the edge divided by the odds. Betting more than Kelly raises variance without raising growth, and betting far more eventually ruins the bankroll even when every single bet has positive expectancy.
EOF

cat > "04 - Permanent/Fractional Kelly reduces drawdowns.md" <<'EOF'
---
created: 2026-10-05
type: permanent
tags: [investing]
---
# Fractional Kelly reduces drawdowns

Betting half of the Kelly fraction keeps about three quarters of the growth rate while cutting the depth of drawdowns sharply. I use half Kelly because my edge estimates are noisy, and overestimating the edge under full Kelly is how bankrolls get wrecked.
EOF

cat > "04 - Permanent/Ergodicity economics.md" <<'EOF'
---
created: 2026-10-08
type: permanent
tags: [investing]
---
# Ergodicity economics

Ergodicity economics asks whether the average over many people equals the average of one person over time. For multiplicative bets it does not: the time-average growth rate of a single bankroll is lower than the ensemble average, which is why maximizing expected value alone is a bad rule for repeated gambles.
EOF

# Shares only the word "criterion" with the target, so it is a coincidental overlap.
cat > "04 - Permanent/Criterion validity in psychometrics.md" <<'EOF'
---
created: 2026-09-12
type: permanent
tags: [psychology]
---
# Criterion validity in psychometrics

Criterion validity measures how well a test score predicts an outcome that is measured separately, such as job performance. Concurrent validity compares the score with a criterion measured at the same time, predictive validity with one measured later.
EOF

cat > "04 - Permanent/CSS grid auto-fit collapses empty tracks.md" <<'EOF'
---
created: 2026-08-20
type: permanent
tags: [css]
---
# CSS grid auto-fit collapses empty tracks

With auto-fit, empty grid tracks collapse to zero width and the remaining items stretch to fill the row, while auto-fill keeps the empty tracks. I use auto-fit for card galleries so a short last row does not leave a hole.
EOF

cat > "04 - Permanent/Rust borrow checker rejects aliased mutation.md" <<'EOF'
---
created: 2026-07-15
type: permanent
tags: [rust]
---
# Rust borrow checker rejects aliased mutation

The borrow checker allows either many shared references or exactly one mutable reference to a value at a time. Most of the errors I hit early on were me trying to hold a mutable reference while another one was still alive.
EOF

cat > "inbox/Sourdough hydration.md" <<'EOF'
At 75% hydration my sourdough crumb is open but the dough is still easy to shape. Going up to 80% made it too slack for a free-standing loaf.
EOF
