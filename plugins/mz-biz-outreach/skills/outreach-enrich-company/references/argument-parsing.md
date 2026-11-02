# Argument Parsing

Extract from `$ARGUMENTS`:

- **user_path** — the path token (everything not matching a parameter pattern). Must end in `.md`.
- **channels_override** — from `channels:<value>` (default: unset → per-contact auto-detect).
- **sender_override** — from `sender:<value>` (default: unset → use strategy.json or fallback voice).
- **enrich_mode** — from `enrich:<value>`: `only`, `skip`, or unset (default unset = both phases run).
- **brief_run** — optional, from `brief:<run_name>`; resolves to `<PROJECT_ROOT>/.mz/outreach/<brief_run>/climate.json` (default: unset).
- **personality_mode** — from `personality:<value>`: `off` disables reader-style calibration; any other value or absent = `on` (default).

## Source resolution

Extract the company slug from `user_path`'s basename:

- If the basename matches `<YYYY-MM-DD>_<slug>.md` (active path), `company_slug` = the part after the date prefix.
- Otherwise (`<slug>.md`), `company_slug` = the basename minus `.md`.

Then resolve `source_path` (the file actually read and updated by this run):

```bash
mkdir -p "<PROJECT_ROOT>/.mz/outreach/active"
find "<PROJECT_ROOT>/.mz/outreach/active" -maxdepth 1 -type f \
  -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<company_slug>.md' 2>/dev/null | head -1
```

- **If found** → `source_path` = the active path returned. The user-supplied path is ignored in favor of the active version (which holds the canonical accumulated history). The user may have passed a now-deleted research-baseline path; the active version is authoritative.
- **If not found** → `source_path` = `user_path`. The card has not been activated yet; this run will activate it.

Validate the card at `source_path` before any other work:

1. The file exists (Read succeeds).
1. The first non-empty line starts with `# ` (H1 = company name).
1. The body contains H2 headers matching the canonical card shape — at minimum `## Overview`, `## Key Contacts`, `## Outreach Recommendation` must all be present. If any are missing, emit `STATUS: BLOCKED` with the list of missing headers.
