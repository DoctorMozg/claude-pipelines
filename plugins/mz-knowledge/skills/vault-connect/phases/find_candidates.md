# Phase 1: Find Link Candidates

## Goal

Find existing vault notes that should be linked to or from the target note. Dispatch `link-suggester` for the target note with inbound links enabled. Collect proposals for the Phase 1.5 approval gate.

## Step 1: Prepare target preview

Read the target note. Strip the frontmatter. Take the first `TARGET_PREVIEW_WORDS` (500) words of body as the preview that the dispatch prompt embeds. Capture the title from frontmatter `title:` if present, else from the first `# ` heading, else from the filename (stem only).

## Step 2: Dispatch `link-suggester`

Dispatch the `link-suggester` agent (model: sonnet) with this task-specific prompt:

```
target_notes:
  - title: "<title>"
    path: "<absolute path>"
vault_path: <vault_path>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/link_proposals.md
task_name: <task_name>
inbound: true

Target preview (first 500 words):
<preview>

Your task: find existing vault notes this note should link to, and notes that should link back to it. Skip any candidate whose relationship you cannot justify in one sentence from both notes' content.
```

After the agent returns, act on its terminal `STATUS:` line before reading the artifact:

- `DONE` → continue with Step 3.
- `DONE_WITH_CONCERNS` → the vault has fewer than 10 permanent notes, so the proposals are thin. Record `SmallVault: true` in `state.md`, continue with Step 3, and surface the small-vault concern in the Phase 1.5 gate.
- `NEEDS_CONTEXT` → this dispatch left out the field the agent names. Fill it in from `state.md` and re-dispatch once; if the agent asks again, handle it as `BLOCKED`.
- `BLOCKED` → the vault root or the target note is unreadable at the path the agent quotes. Ask via AskUserQuestion whether to re-dispatch with a corrected path or abort; on abort set `Status: aborted_by_user` and stop.
- No status line, or one not listed here → handle it as `BLOCKED`.
- No answer to a question above → set `Status: blocked` with the open question in `what_remains` and stop. A missing answer is never approval.

## Step 3: Validate and hand off

1. Read `<PROJECT_ROOT>/.mz/task/<task_name>/link_proposals.md`.
1. Validate structure against the output format in the link-suggester agent definition: a `links:` list with one entry, whose `source_path` is the target note; that entry has `source_title`, `source_path` and a `targets` list; each target has `direction`, `target_title`, `target_path`, `relationship` and `reason`; `direction` is `outbound` or `inbound`; `relationship` is one of the six allowed values.
1. If the file is missing, malformed, or its `targets` list is empty, retry the dispatch once with a clarified prompt. If still empty, surface the empty result via AskUserQuestion per the SKILL.md error handling — do not silently claim nothing to link.
1. Update `state.md`: `Phase: 1`, `OutboundProposed: <N>`, `InboundProposed: <N>`, counting targets by `direction`.

Return to SKILL.md Phase 1.5 gate with the proposals formatted for the user-facing presentation (letter-labelled list, grouped by `direction`).

## Error handling

- **Target note unreadable** → escalate via AskUserQuestion; never dispatch the agent with a stale path.
- **Agent returns malformed YAML** → retry once with a pointer to the output format in the link-suggester agent definition. Log the retry in `state.md`.
