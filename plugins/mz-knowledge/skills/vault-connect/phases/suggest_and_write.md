# Phase 2: Write Approved Links

## Goal

Write wikilinks for every proposal that survived the Phase 1.5 gate. Outbound links go into the target note, inbound links go into the existing notes that should link back to it. Prefer in-body placement near the relevant paragraph; fall back to a `## Related` section.

## Step 1: Filter approved proposals

Read `<PROJECT_ROOT>/.mz/task/<task_name>/link_proposals.md` and the Phase 1.5 decision (`approve` for all, or a letter-skip list). Its one `links` entry describes the skill's target note (`source_title`, `source_path`). Drop any proposal in its `targets` list whose letter was skipped. The remaining targets are the write set: those whose `direction` is `outbound` go to Step 2, those whose `direction` is `inbound` go to Step 3.

## Step 2: Write outbound links (target note)

For each approved outbound proposal:

1. Read the target note fresh — context may have shifted.
1. Decide placement:
   - **In-body**: scan the body for a paragraph whose topic matches the `reason` (shared key term or claim). Insert `[[<target_title>]]` as a wikilink inline in that paragraph, keeping surrounding prose intact.
   - **Related section**: if no paragraph matches, append to a `## Related` section at the end of the note. Create the section if it does not exist, with a blank line before the header. Add a bullet: `- [[<target_title>]] — <relationship>` where `<relationship>` is one of the six typed labels.
1. Never modify the frontmatter for link purposes. Never use markdown `[text](path)` syntax — only `[[wikilink]]`.
1. Write the updated file. Re-read to confirm the link is present exactly once.

Cap in-body insertions per paragraph at one — never stack multiple wikilinks into the same sentence.

## Step 3: Write inbound links (existing notes)

For each approved inbound proposal, the note to edit is the existing note at the proposal's `target_path`, and the link points back at the skill's target note, `source_title`.

1. Read the existing note fresh.
1. Decide placement using the same rule as Step 2:
   - **In-body**: insert `[[<source_title>]]` inline in the paragraph whose topic matches the `reason`.
   - **Related section**: if no paragraph matches, append/extend the existing note's `## Related` section with `- [[<source_title>]] — <relationship>`.
1. Frontmatter untouched. Wikilink syntax only. Re-read to confirm.

If multiple inbound proposals share one `target_path` (rare with `MAX_INBOUND_LINKS = 3`), write them in one pass — read once, edit once, write once.

## Step 4: Update state and finalize

Update `state.md`:

```
schema_version: 2
Status: complete
Phase: 2
Completed: <ISO timestamp>
OutboundWritten: <N>
InboundWritten: <N>
Skipped: <N>   # proposals the user skipped via letter list
phase_complete: true
what_remains: []
```

Write `<PROJECT_ROOT>/.mz/task/<task_name>/session_summary.md` with the final list of writes:

```yaml
target:
  title: "Target Title"
  path: "<absolute path>"
writes:
  - direction: outbound
    to_title: "Existing Note A"
    to_path: "<absolute path>"
    relationship: extends
    placement: in-body|related-section
  - direction: inbound
    from_title: "Existing Note C"
    from_path: "<absolute path>"
    relationship: example-of
    placement: in-body|related-section
```

## Step 5: Print the final block

```
vault-connect complete:
  Note: [[<target title>]]
  Outbound links added: <N>
  Inbound links added: <N>
  Skipped: <N>
  Task dir: .mz/task/<task_name>/
```

## Error handling

- **Wikilink already present** (target title already linked in the destination) → skip that write, record `placement: already-present` in `session_summary.md`, continue.
- **Note at a `target_path` missing or moved** between Phase 1 and Phase 2 → record `placement: source-missing`, continue; do not abort the whole session.
- **Edit fails** (collision or malformed body) → report the exact failure via AskUserQuestion and offer to retry or skip that write.
