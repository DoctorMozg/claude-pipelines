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

Update `state.md` once all approved notes are written: `Phase: 2`, `NotesWritten: <N>`.

## Step 2: Dispatch link-suggester

Dispatch the `link-suggester` agent (model: sonnet) with the prompt below. This agent searches the vault for existing notes that each new note should link to.

```
target_notes:
  - title: "<title from TitleToPath>"
    path: "<absolute path from TitleToPath>"
  <one entry per TitleToPath item in state.md>
vault_path: <vault_path>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/link_proposals.md
task_name: <task_name>
inbound: false

Your task: these notes were just written. Find existing vault notes each of them should reference via [[wikilinks]], at most 5 per note. Skip candidates whose relationship you cannot justify in one sentence from read content.
```

After the agent returns, act on its terminal `STATUS:` line before reading the artifact:

- `DONE` → validate the artifact as below.
- `DONE_WITH_CONCERNS` → the vault has fewer than 10 permanent notes, so the proposals are thin. Record `SmallVault: true` in `state.md`, then validate the artifact as below.
- `NEEDS_CONTEXT` → this dispatch left out the field the agent names. Fill it in from `state.md` and re-dispatch once; if the agent asks again, handle it as `BLOCKED`.
- `BLOCKED` → the vault root or a new note is unreadable at the path the agent quotes. Ask via AskUserQuestion whether to re-dispatch with a corrected path or finish without links. On finish, set `Status: complete`, `LinksAdded: 0`, `LinksSkipped: true`, `LinkSuggesterBlocked: <the agent's reason>`, and print the final output block.
- No status line, or one not listed here → handle it as `BLOCKED`.
- No answer to a question above → set `Status: blocked` with the open question in `what_remains` and stop. A missing answer is never approval.

Read `<PROJECT_ROOT>/.mz/task/<task_name>/link_proposals.md` and validate structure against the output format in the link-suggester agent definition: a `links:` list with one entry per new note; each entry has `source_title`, `source_path` and a `targets` list; each target has `direction`, `target_title`, `target_path`, `relationship` and `reason`, and its `direction` is `outbound`. Update `state.md`: `Phase: link_proposals_ready`.

Return to SKILL.md Phase 2.5 with the proposals formatted for the user-facing presentation.

## Step 3: Apply approved links

After the user approves in Phase 2.5 (with optional per-link skips), apply approved links to the already-written notes:

1. Group approved targets by `source_path`.
1. For each source note:
   - Read the note file.
   - If the body already contains a `## Related` section, append new `- [[<target_title>]] — <relationship>` lines below it, preserving existing links.
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
