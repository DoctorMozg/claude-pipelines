## Memory File Hygiene

Memory files (`CLAUDE.md`, `MEMORY.md`, anything under a project's `memory/` or `.mz/memory/` directory) accumulate over time and start consuming context budget that belongs to actual work. Compress proactively when they cross a size threshold — but only the prose. Code, paths, structured data, and list/table structure stay verbatim.

## When to Compress

Trigger compression when any of these are true:

- `CLAUDE.md` exceeds 300 lines
- `MEMORY.md` exceeds 150 entries
- Any single memory file exceeds 200 lines
- A session-start scan shows the memory surface above 8K tokens

Same-day re-trigger is fine — compression is idempotent against already-compressed text.

## What to Compress

Apply only to plain prose: bullet bodies, paragraphs, summaries, descriptions, hooks.

- Drop articles (a/an/the) where meaning is preserved
- Drop hedging adverbs (just/really/basically/quite/somewhat/actually)
- Drop pleasantries and throat-clearing
- Drop redundant phrasing — never two ways to say the same thing
- Use fragments where a complete sentence is unnecessary
- Use arrows (`X -> Y`) for transitions and causation

## Preserve Verbatim

Never touch:

- Code blocks and inline code
- URLs, file paths, command lines, flags, environment variables
- Frontmatter (YAML), JSON blocks, structured data
- Version strings, dates, proper nouns, technical terms
- Headings, list markers, table structure

If a line contains a path, command, or version, leave the surrounding prose alone too — readability around load-bearing identifiers matters more than the saved tokens.

## Backup Before Overwriting

Before writing the compressed version, save the original to `<filename>.original.md` in the same directory. The backup is the recovery path if compression damages meaning. Do not commit `.original.md` files — add the pattern to `.gitignore` if not already present.

## What Not to Touch

Do not auto-compress:

- Source code (`*.py`, `*.ts`, `*.js`, `*.go`, `*.rs`, `*.cpp`, etc.)
- Configuration (`*.json`, `*.yaml`, `*.toml`, `*.ini`)
- Generated files (lockfiles, build outputs, transcripts)
- Files outside the memory boundary — only `.md` and `.txt` memory files are in scope

When in doubt, leave the file alone and ask.
