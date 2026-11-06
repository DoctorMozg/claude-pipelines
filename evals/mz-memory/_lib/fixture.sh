#!/usr/bin/env bash
# Fixture helpers that case scaffolds source. They run in the empty eval workspace.
# Keep a fixture under 5 Lessons bullets and 300 MEMORY.md lines: past either, SessionEnd detaches a paid
# curator or compressor run, and a case can't set MZ_MEMORY_COMPRESS=0 because its env takes only EVAL_* keys.

# mz-memory resolves the project root to the nearest .git, and the eval's HOME is a git repo,
# so a workspace without its own repo would read and write HOME's .mz instead.
init_project() {
  git init -q
  git -c user.name=eval -c user.email=eval@example.invalid commit -q --allow-empty -m init
}

# write_memory PINNED LOG: each argument holds the region's lines, newest first; either may be empty.
write_memory() {
  mkdir -p .mz/memory
  {
    printf '# Project Memory\n\n<!-- Auto-managed by mz-memory. Most recent first. -->\n<!-- mz-memory:v2 -->\n\n'
    printf '## Pinned\n\n<!-- mz-pinned-start -->\n'
    [[ -n "$1" ]] && printf '%s\n' "$1"
    printf '<!-- mz-pinned-end -->\n\n## Activity Log\n\n<!-- mz-log-start -->\n'
    [[ -n "$2" ]] && printf '%s\n' "$2"
    printf '<!-- mz-log-end -->\n'
  } > .mz/memory/MEMORY.md
}

# write_lessons CURATED INBOX: "- [L-…]" and "- [I-…]" lines for lessons.md's two regions; either may be empty.
write_lessons() {
  mkdir -p .mz/memory
  {
    printf '# Project Lessons\n\n<!-- Auto-managed by mz-memory. Curated lessons first; new lessons wait in the Inbox. -->\n\n'
    printf '## Lessons\n\n<!-- mz-lessons-start -->\n'
    [[ -n "$1" ]] && printf '%s\n' "$1"
    printf '<!-- mz-lessons-end -->\n\n## Inbox\n\n<!-- mz-inbox-start -->\n'
    [[ -n "$2" ]] && printf '%s\n' "$2"
    printf '<!-- mz-inbox-end -->\n'
  } > .mz/memory/lessons.md
}

# write_task NAME STATUS: writes .mz/task/NAME/state.md; the sections after the header come from stdin.
write_task() {
  mkdir -p ".mz/task/$1"
  {
    printf '# %s\n\nStatus: %s\nPhase: done\n\n' "$1" "$2"
    cat
  } > ".mz/task/$1/state.md"
}
