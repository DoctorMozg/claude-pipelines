# Phase 2: Write Fleeting Note to Vault

## Goal

After the user approved the transcript in Phase 1.5, build a fleeting-note file with full provenance frontmatter, sanitize the filename, write the note to `<vault>/<INBOX_FOLDER>/`, and offer a follow-up to run `process-notes` on the newly captured note.

## Step 1: Derive the title

The title becomes both the filename and the frontmatter `title:` field.

1. Read `.mz/task/<task_name>/transcript.md` (re-read — context may have shifted since Phase 1.5).

1. Extract the transcript body (everything after the closing `---` of the frontmatter block).

1. Derive a candidate title from the first meaningful line of the body:

   - Skip empty lines and lines containing only noise markers like `[inaudible]`, `[unclear]`, or bare page numbers.
   - Take the first sentence (ends at `.`, `!`, `?`, or end-of-line) of the first meaningful line.
   - Truncate to 70 characters at a word boundary, trim trailing punctuation and whitespace.

1. If the candidate title is empty or obviously low-signal (`<5 words`), ask via AskUserQuestion:

   ```
   Transcript has no clear opening sentence to use as a title.

   First 200 characters of transcript body:
   <paste verbatim>

   Options:
     - "use-timestamp" — fall back to "<modality> capture <YYYY-MM-DD HH:MM>".
     - "custom" — I will provide a title.
   ```

   On `custom`, accept the user's reply as the title. On `use-timestamp`, build the title as `"<modality> capture <YYYY-MM-DD HH:MM>"` using the `captured_at` field from the transcript frontmatter.

Record the final title in `state.md` under `DerivedTitle: "<title>"`.

## Step 2: Sanitize the filename

Apply the same sanitization `process-notes` uses so filenames are consistent across capture and atomization:

1. Lowercase the title.
1. Replace whitespace with hyphens.
1. Strip any character outside `[a-z0-9-]`.
1. Collapse consecutive hyphens into a single hyphen.
1. Truncate to 60 characters, then trim trailing hyphens.
1. Append `.md`.
1. Resolve collisions: if `<vault>/<INBOX_FOLDER>/<filename>.md` already exists, append `-2`, `-3`, ... before `.md` until the path is free.

Record the resolved filename in `state.md` under `DerivedFilename: <filename>.md`.

## Step 3: Build the fleeting-note content

Compose the full file contents with frontmatter and body. The frontmatter below is mandatory — every field listed must be present, even when the value is empty.

```yaml
---
title: "<DerivedTitle>"
created: <YYYY-MM-DD>
type: fleeting
source: "<input path or URL>"
source_type: <voice|image|pdf|youtube|screenshot>
captured_at: <ISO timestamp from transcript frontmatter>
tags: [inbox]
status: draft
---

<transcript body, verbatim from transcript.md, with the transcript's own frontmatter stripped>
```

Field rules:

- `title`: the DerivedTitle wrapped in double quotes. Escape embedded double quotes per YAML rules.
- `created`: the local date portion of `captured_at` formatted as `YYYY-MM-DD`.
- `type: fleeting`: always literal — `vault-ingest` never writes `permanent` or `evergreen`. Promotion is an explicit user step run via `process-notes`.
- `source`: the exact input path or URL the user provided, quoted.
- `source_type`: the captured modality. Use `screenshot` instead of `image` only when the user confirmed (in Phase 0) that the image is a screenshot — otherwise use the raw modality value.
- `captured_at`: copy directly from the transcript frontmatter (ISO 8601).
- `tags: [inbox]`: always literal. The `inbox` tag is what triage and search rely on to surface newly captured notes.
- `status: draft`: always literal. Every vault write from this skill is a draft; the user promotes manually.

Do not append any body content beyond the verbatim transcript. No summaries, no headings, no "captured via vault-ingest" footers.

## Step 4: Write to the vault

1. Ensure `<vault>/<INBOX_FOLDER>/` exists. If missing, create it with `Bash` (`mkdir -p`). Note the creation in `state.md` under `InboxCreated: true` when applicable.
1. Use the `Write` tool to create `<vault>/<INBOX_FOLDER>/<filename>.md` with the composed content from Step 3.
1. Re-read the written file with `Read` and verify:
   - The file exists.
   - The frontmatter block parses.
   - Every required frontmatter field from Step 3 is present with a non-placeholder value.
   - The body matches the transcript body.
1. If verification fails, emit a clear error and record `FileWriteError: <one-line error>` in `state.md`. Do not proceed to Step 5.

Update `state.md`: `Phase: 2`, `Status: note_written`, `NotePath: <absolute path to the written file>`.

## Step 5: Offer a follow-up

Before marking the run complete, offer the user a single follow-up choice via AskUserQuestion:

```
Fleeting note captured at <NotePath>.

Run `/process-notes` now to atomize this capture into permanent notes?

Options:
  - "yes" — I will invoke process-notes on the new note immediately after this run completes.
  - "no" — leave the note in the inbox; you will handle it later.
  - "later" — keep the note but remind me on the next /vault-triage run (no-op in this skill, but recorded in state).
```

Response handling:

- **"yes"** → record `FollowUp: run-process-notes` in `state.md`. The orchestrator SHOULD then suggest the exact command `/process-notes <NotePath>` as part of the terminal output. Do not dispatch `process-notes` from inside this skill — the user runs it as a separate skill invocation.
- **"no"** → record `FollowUp: none`. Proceed to completion.
- **"later"** → record `FollowUp: defer-to-triage`. Proceed to completion.

## Step 6: Finalize state and print verification block

Update `state.md` to terminal:

```yaml
Status: complete
Phase: 2
Completed: <ISO timestamp>
NotePath: <absolute path>
Modality: <voice|image|pdf|youtube|screenshot>
ToolUsed: <tool name from transcript.md frontmatter>
SourceType: <source_type written to the note>
FollowUp: <run-process-notes|none|defer-to-triage>
```

Print the final orchestrator block (this block is the Verification output for the skill):

```
vault-ingest complete:
  Note: <NotePath>
  Modality: <modality>  (source_type: <source_type>)
  Tool used: <tool name>
  Location: <vault>/<INBOX_FOLDER>/
  Status: draft (inbox) — run /process-notes on this note when ready
  Task dir: .mz/task/<task_name>/
```

## Constraints

- Never overwrite an existing vault file. Always resolve collisions by appending `-2`, `-3`, ... suffixes.
- Never change `type:` to anything other than `fleeting` in this skill — promotion happens elsewhere.
- Never drop the `inbox` tag or `status: draft` on write. Both are load-bearing for downstream skills.
- Never skip the re-read verification in Step 4. Silent write failures corrupt the inbox.
- Never dispatch `process-notes` from inside this phase. The follow-up offer is a user-facing suggestion, not an automated chain.
