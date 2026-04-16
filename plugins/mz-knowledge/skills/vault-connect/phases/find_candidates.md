# Phase 1: Find Link Candidates

## Goal

Find existing vault notes that should be linked to or from the target note. Dispatch `link-suggester` with the target content and typed-relationship instructions. Collect proposals for the Phase 1.5 approval gate.

## Step 1: Prepare target preview

Read the target note. Strip the frontmatter. Take the first `TARGET_PREVIEW_WORDS` (500) words of body as the preview that the dispatch prompt embeds. Capture the title from frontmatter `title:` if present, else from the first `# ` heading, else from the filename (stem only).

## Step 2: Dispatch `link-suggester`

Dispatch the `link-suggester` agent (model: sonnet) with this task-specific prompt:

```
Target note:
  title: "<title>"
  path: "<absolute path>"
  content (first 500 words):
<preview>

Vault path: <vault_path>
Task dir: .mz/task/<task_name>/

Your task:

Find existing vault notes that should be linked to or from this target note. Do NOT propose links to notes you have not actually read — every proposal must be grounded in both notes' content.

Steps:

1. Extract 5-10 key terms and concepts from the target note (titles, named entities, domain terms, distinctive phrases).
2. Search the vault for notes mentioning these terms — grep both filenames and body content.
3. Read up to 15 top matching notes (first 200 words each).
4. For each match, decide two things independently:
   - Should the TARGET note link to it? (Yes if the target discusses a concept this match explains or extends.)
   - Should the MATCH link back? (Yes if the match discusses something the target exemplifies, extends, or refutes.)
5. Assign a relationship type from this closed set:
   supports | contradicts | extends | example-of | prerequisite-for | see-also
6. Skip any candidate whose relationship you cannot justify in one sentence from the read content.

Caps:
- At most 5 outbound proposals (links to add TO the target).
- At most 3 inbound proposals (links to add FROM other notes TO the target).
- Never propose linking the target to itself.

Write proposals to `.mz/task/<task_name>/link_proposals.md` using exactly this YAML shape:

target:
  title: "Target Title"
  path: "<absolute path>"
outbound_links:
  - title: "Existing Note A"
    path: "<absolute path>"
    relationship: "extends"
    reason: "One sentence grounded in both notes' content."
inbound_links:
  - title: "Existing Note C"
    path: "<absolute path>"
    relationship: "example-of"
    reason: "One sentence grounded in both notes' content."

Terminal status:
- STATUS: DONE with link_proposals.md written.
- STATUS: DONE_WITH_CONCERNS if the vault contains fewer than 10 readable notes — still write the file with whatever was found, flag the small-vault concern.
- STATUS: NEEDS_CONTEXT only if the target note or vault root is missing or unreadable.
```

## Step 3: Validate and hand off

After the agent returns:

1. Read `.mz/task/<task_name>/link_proposals.md`.
1. Validate structure: top-level `target`, `outbound_links`, and `inbound_links` keys; each entry has `title`, `path`, `relationship`, `reason`; `relationship` is one of the six allowed values.
1. If the file is missing, malformed, or empty on both link lists, retry the dispatch once with a clarified prompt. If still empty, surface the empty result via AskUserQuestion per the SKILL.md error handling — do not silently claim nothing to link.
1. Update `state.md`: `Status: candidates_found`, `Phase: 1`, `OutboundProposed: <N>`, `InboundProposed: <N>`.

Return to SKILL.md Phase 1.5 gate with the proposals formatted for the user-facing presentation (letter-labelled list, grouped by direction).

## Error handling

- **Target note unreadable** → escalate via AskUserQuestion; never dispatch the agent with a stale path.
- **Agent returns malformed YAML** → retry once with a reminder of the exact shape. Log the retry in `state.md`.
- **Agent STATUS: NEEDS_CONTEXT** → forward the agent's required-context list to the user via AskUserQuestion; do not attempt to fabricate the missing input.
