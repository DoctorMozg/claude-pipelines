# Phase 2: Link and Write

## Goal

Write approved draft notes to the vault, then dispatch the `link-suggester` agent to propose `[[wikilinks]]` from each new note to existing vault notes. After Phase 2.5 approval, apply the approved links and finalize the run.

## Step 1: Write approved drafts to the vault

Filter `proposals.md` by the Phase 1.5 approval decision (all notes if `approve`, subset if numbers were skipped). For each approved draft:

1. Determine the target folder from vault CLAUDE.md conventions. Typical layouts: `04 - Permanent/`, `permanent/`, `notes/permanent/`. If the vault has no explicit convention, default to `<vault>/permanent/` and record the choice in `state.md` under `TargetFolder`.
1. Sanitize the filename from the claim title:
   - Lowercase.
   - Replace whitespace with hyphens.
   - Strip any character outside `[a-z0-9-]`.
   - Collapse consecutive hyphens to one.
   - Truncate to `MAX_FILENAME_CHARS` (60) characters, trim trailing hyphens.
   - Append `.md`.
   - If the resulting filename collides with an existing vault file, append `-2`, `-3`, ... before `.md` until free.
1. Write the draft body (frontmatter + content, exactly as produced in Phase 1) to `<vault>/<target-folder>/<filename>.md`. Preserve `status: draft` in the frontmatter — the user promotes to `evergreen` manually when ready.
1. Append the written path to `state.md` under `FilesWritten:` (YAML list). Also record each `title -> path` mapping under `TitleToPath:` for the link-suggester dispatch.

Update `state.md` once all approved notes are written: `Phase: 2`, `Status: notes_written`, `NotesWritten: <N>`.

## Step 2: Dispatch link-suggester

Dispatch the `link-suggester` agent (model: sonnet) with the prompt below. This agent searches the vault for existing notes that each new note should link to.

```
New notes written (title → path mapping):
<paste TitleToPath block from state.md as a YAML list>

Vault root: <vault_path>
Task dir: .mz/task/<task_name>/

Your task:

For each new note, scan the vault for existing notes that the new note should reference via [[wikilinks]]. For every candidate target, record:
- Source note title (one of the new notes)
- Target note title (existing vault note)
- Relationship type, chosen from: supports | contradicts | extends | example-of | prerequisite-for | see-also
- One-sentence reason grounded in the actual content of both notes — not a guess

Caps:
- At most 5 link suggestions per new note.
- Do not propose links between two new notes at this stage — that is a separate pass.
- Skip candidates whose relationship you cannot justify in one sentence from read content.

Write proposals to `.mz/task/<task_name>/link_proposals.md` using exactly this YAML shape:

links:
  - source_title: "First new note title"
    source_path: "<absolute path>"
    targets:
      - target_title: "Existing Vault Note"
        target_path: "<absolute path>"
        relationship: "extends"
        reason: "One sentence..."
      - ...
  - source_title: "Second new note title"
    source_path: "<absolute path>"
    targets: []

Terminal status:
- STATUS: DONE with `link_proposals.md` written.
- STATUS: DONE_WITH_CONCERNS if the vault contains fewer than 10 readable notes — still write the file with whatever was found, but flag the small-vault concern.
- STATUS: NEEDS_CONTEXT only if the vault root is missing or unreadable.
```

After the agent returns, read `.mz/task/<task_name>/link_proposals.md` and validate structure (`links:` list, each entry has `source_title`, `source_path`, `targets` list). Update `state.md`: `Status: link_proposals_ready`.

Return to SKILL.md Phase 2.5 with the proposals formatted for the user-facing presentation.

## Step 3: Apply approved links

After the user approves in Phase 2.5 (with optional per-link skips), apply approved links to the already-written notes:

1. Group approved targets by `source_path`.
1. For each source note:
   - Read the note file.
   - If the body already contains a `## Related` section, append new `- [[Target Title]] — <relationship>` lines below it, preserving existing links.
   - If no `## Related` section exists, append one to the end of the body with a blank line before the header.
   - Preserve the frontmatter block untouched. Never move or rewrite existing content — only append to the Related section.
1. Update `state.md`: `Phase: 2`, `Status: complete`, `Completed: <ISO timestamp>`, `LinksAdded: <N>`.

If Phase 2.5 returns `reject` for links, leave the notes as written in Step 1 without a Related section. Mark `state.md`: `Status: complete`, `LinksAdded: 0`, `LinksSkipped: true`.

## Final output

Print exactly this block as the terminal orchestrator message, filled with actual counts and paths:

```
process-notes complete:
  Notes written: <N>
  Location: <vault>/<target-folder>/
  Links added: <N>
  Status: draft (promote to evergreen when reviewed)
  Task dir: .mz/task/<task_name>/
```

This block is the Verification checkpoint for the skill — the user sees it and can re-check that drafts, links, and state all landed.
