---
name: outreach-update-card
description: ALWAYS invoke when the user wants to log an outreach action against a company card .md (created by outreach-research). Appends a dated one-line entry to the card's Interaction History section, then relocates the card to the active folder with today's date prefix. Triggers - "log action on <card>", "update card with <action>", "record interaction on <card>", "I just <action>, add it to <card>".
argument-hint: "<path/to/card.md>" "<action description>"
model: haiku
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# Outreach Update Card

## Overview

You append a one-line, dated interaction entry to a company card produced by `/outreach-research`, then relocate the card to `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md` where the date prefix is today (the last interaction date). The entry lands under a `## Interaction History` section at the bottom of the card (creating the section if it does not exist).

The skill is atomic — one entry, one write, one cleanup, no agents, no follow-up phases.

## When to Use

Invoke when the user has taken an outreach action against a company they hold a card for, and wants the action recorded on the card. Trigger phrases include:

- "log my call with Acme — they're interested, here's the card path"
- "update <card path> — sent intro email to John"
- "record on the Acme card: replied to John's question about pricing"
- "I just left a voicemail at <card path>, add it"

### When NOT to use

- The user wants to *create* a new company card → invoke `outreach-research` for that one company instead.
- The user wants to *draft* an outreach letter → invoke `outreach-contacts`.
- The user wants to remember the action only in conversation context, not in a card → do not invoke this skill.
- The target file is not a company card (missing `## Overview` and `## Outreach Recommendation` headers) → emit `STATUS: BLOCKED`.

## Directory Lifecycle

Cards move through two directories:

- **Research baseline** — `.mz/outreach/<run>/companies/<slug>.md`. Output of `/outreach-research`. Untouched by this skill until first activation.
- **Active** — `.mz/outreach/active/<YYYY-MM-DD>_<slug>.md`. Where this skill writes. The date prefix is the last interaction date. The slug is the company slug (stripped of any prior date prefix).

A card is "active" the moment any interaction is logged or letters are drafted against it. This skill is one of two entry points that move a card into `active/` (the other is `/outreach-contacts`).

## Core Process

### Step 1: Parse arguments

`$ARGUMENTS` is expected as two parts:

1. **Card path** (first positional token) — path to an existing `.md` file. Either a research-baseline path (`.mz/outreach/<run>/companies/<slug>.md`) or an active path (`.mz/outreach/active/<date>_<slug>.md`). If missing, emit `STATUS: BLOCKED: card path required` and stop.

1. **Action description** (remainder of `$ARGUMENTS`) — the verbatim wording the user supplied. If absent, prompt via `AskUserQuestion`:

   > What action do you want logged on `<card filename>`?

Strip surrounding quotes from the description if the user passed them. Otherwise preserve the wording exactly — do not paraphrase, expand, or categorize.

### Step 2: Resolve slug and source path

Extract the company slug from the user-supplied path's basename:

- If the basename matches `<YYYY-MM-DD>_<slug>.md` (active path), `slug` = the part after the date prefix.
- Otherwise (`<slug>.md`, e.g. a research-baseline path), `slug` = the basename minus the `.md` extension.

Run `mkdir -p .mz/outreach/active` so the directory exists.

Find any existing active card for this slug:

```bash
find .mz/outreach/active -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<slug>.md' 2>/dev/null | head -1
```

- **If found**: `source_path` = the active path returned. The user-supplied path is ignored in favor of the active version (which has the canonical accumulated history).
- **If not found**: `source_path` = the user-supplied path. The card has not been activated yet.

### Step 3: Validate the card

Read the file at `source_path`. Verify:

1. The Read succeeded (file exists).
1. The body contains both `## Overview` AND `## Outreach Recommendation` as H2 headings somewhere.

If either check fails, emit:

```
STATUS: BLOCKED: target is not a company card (missing canonical headers or file not found at <source_path>)
```

and stop.

### Step 4: Resolve today's date

Run `date +%Y-%m-%d` via the Bash tool. Use the literal output as the entry date and the target filename prefix — never infer or pull from conversation context.

### Step 5: Compose the entry

Format the entry as a single line:

```
- **<YYYY-MM-DD>** — <action description>
```

Use an em-dash (`—`, U+2014), not a hyphen. Preserve the action description exactly as the user wrote it (capitalization, punctuation, channel tags, emoji). If the description does not end with sentence-ending punctuation, do not add any.

### Step 6: Update card content and write to target

Compute `target_path` = `.mz/outreach/active/<today>_<slug>.md`.

Detect whether the card body (read in Step 3) already contains a `## Interaction History` H2 section:

**Case A — section exists**: locate the heading line. Find the end of the section (the next H2 heading line, or end-of-file). Insert the new entry as the last bullet under `## Interaction History`, preserving chronological order (oldest at top, newest at bottom). If the section has only the heading and no bullets yet, the new entry becomes the first bullet.

**Case B — section absent**: append at the very end of the file, after any existing footer lines (`*Generated: …*`, `*Letters generated: …*`, etc.):

```
<blank line>
## Interaction History

- **<YYYY-MM-DD>** — <action description>
```

The card must end with a single trailing newline.

Write the updated content to `target_path` using `Write` (full-file write, atomic). If `target_path` already exists (re-run on same day), the Write overwrites it cleanly — the in-memory copy from Step 3 was already read from `target_path` in that case, so Write semantics are satisfied.

### Step 7: Cleanup old location

If `source_path != target_path`, the card has moved (either from research baseline to active, or from a stale active date to today's). Remove the old file:

```bash
rm "<source_path>"
```

Also clean up any other stale active entries for this slug (defensive — shouldn't normally exist, but covers manual edits and prior-run corruption):

```bash
find .mz/outreach/active -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<slug>.md' ! -path "<target_path>" -delete 2>/dev/null
```

If `source_path == target_path`, skip cleanup (the file at the target IS the source).

### Step 8: Report

Emit a short verification block:

```
**Card updated**: <absolute path to target_path>
**Moved from**:  <source_path>      # omit this line if source_path == target_path
**Entry added**: - **<date>** — <description>
**Section**:    <"appended to existing" | "newly created">

STATUS: DONE
```

## Common Rationalizations

- "I should auto-categorize the action as email / call / meeting." — No. The user's wording is canonical. Channel tags belong inside the description if the user wrote them.
- "I should look up other contact records and reconcile." — No. This skill writes one card. It does not touch any other file beyond the move-cleanup of the source.
- "The card has malformed sections, let me clean them up while I'm here." — No. Either validate and write only the new entry, or emit `BLOCKED`. Never silently rewrite unrelated structure.
- "The user's description is vague, I'll expand it." — No. Append verbatim. The user is the source of truth for what happened.
- "I'll backdate the entry because the action probably happened yesterday." — No. The date is always today. If the user needs a different date, they pass it in the description body.
- "The research baseline at `companies/<slug>.md` is valuable, I'll keep a copy." — No. The active card contains all of its content plus the appended sections. Cleaning up the source keeps `companies/` honest as the dormant-research layer.
- "An active card from another date exists, I'll leave it alone and create today's alongside." — No. There is one active card per slug. The date prefix is the LAST interaction date; older-dated active files for the same slug get deleted in Step 7.

## Red Flags

- You opened or edited any file other than `source_path` and `target_path`.
- You inferred a date instead of running `date +%Y-%m-%d`.
- You reformatted, rephrased, or relabeled the user's action description.
- You modified any section of the card other than `## Interaction History`.
- You created or moved any `*Generated: …*` or `*Letters generated: …*` footer line.
- You left two active files for the same slug behind (e.g., `2026-05-12_acme.md` AND `2026-05-15_acme.md`).
- You kept the research-baseline `companies/<slug>.md` after relocating its content to active.

## Verification

After writing, re-read `target_path` and confirm:

- `## Interaction History` appears exactly once.
- The new bullet matches the `- **<YYYY-MM-DD>** — <description>` format.
- The previous card content (every line above the appended/extended section) is byte-identical to the in-memory copy you held before the write.

After cleanup, list `.mz/outreach/active/` and confirm exactly one file matches `*_<slug>.md`.

If any check fails, restore the prior content from your in-memory copy with a second `Write` call to the original `source_path`, delete `target_path` if it was newly created, and emit:

```
STATUS: DONE_WITH_CONCERNS: rewrite reverted because <reason>
```
