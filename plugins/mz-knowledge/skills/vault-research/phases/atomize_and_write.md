# Phase 2 & 3: Atomize, Write to Vault, Suggest Links

## Goal

Iterate sequentially over the atomization windows recorded in `parsed_report.md`, dispatching `atomization-proposer` once per window; merge the per-window proposals into a single `proposals.md` capped at `MAX_NOTES`; present those proposals via the Phase 2.5 gate; write approved notes into the vault's permanent folder under a `research/` subfolder; dispatch `link-suggester` on the written note paths; present link suggestions via the Phase 3.5 gate; apply approved links and finalize.

This phase file covers three orchestrator phases: Phase 2 (atomize + post-approval write), Phase 3 (link suggestions), and the apply step that follows the Phase 3.5 gate. Gates 2.5 and 3.5 sit between the steps and are defined in `SKILL.md`.

## Preconditions

Phase 1.5 returned `approve`. `state.md` records `AtomizationWindows: N`, `ParsedReportPath`, `Vault`, `PermanentFolder`, `ReportPath`. `TASK_DIR<task_name>/` exists.

Constants used from `SKILL.md`:

- `MAX_NOTES`: 15 — hard cap on total merged proposals.
- `ATOMIZATION_WAVE_WORD_CAP`: 450 — per-window input ceiling for `atomization-proposer`.
- `TASK_DIR`: `.mz/task/`.

## Step 1: Sequential window iteration (atomize)

Read `state.md`. The `wave_offset` field is the index of the next window to dispatch — default `0`, incremented after each successful dispatch so a resumed run picks up where it left off.

For each window from `wave_offset` to `AtomizationWindows - 1`, in order:

1. Extract the window's text using the `window_boundaries` entry from `parsed_report.md`. If per-window bodies were cached under `.mz/task/<task_name>/windows/window_<N>.md` in Phase 1, Read that file. Otherwise re-parse the report using the recorded `start_section` / `end_section` / word count.

1. Dispatch `atomization-proposer` (model: opus) with the prompt below. Fill placeholders from `state.md`:

   ```
   Input content:
   <paste the window body verbatim — ≤450 words>

   Source path (for frontmatter `source:` field):
   <ReportPath from state.md>

   Vault conventions (from CLAUDE.md):
   <paste permanent folder, frontmatter schema, and tag taxonomy extracted in Phase 0, or "none found">

   Research-report overrides — merge these into every proposal's frontmatter:
     type: research
     source_type: research-report
     report_path: <ReportPath from state.md>

   Output path:
   .mz/task/<task_name>/proposals_window_<wave_offset>.md

   Your task:

   1. DETECT BOUNDARIES: Identify atomic note boundaries in the input.
      - Each atomic note captures exactly one clear idea or claim.
      - When in doubt, split — err toward smaller, linked notes.
      - Cap each note at roughly 500 words of body content.

   2. DRAFT EACH NOTE: For every detected atomic note, write full content:
      - Title: claim-style assertion under 70 characters (not a bare topic).
      - Frontmatter keys: title, created (YYYY-MM-DD), type: research, source_type: research-report, report_path: <ReportPath>, source: <ReportPath>, tags: [], status: draft.
      - Body: 150-400 words in the author's own words, self-contained.
      - Do NOT write wikilinks in the body — linking is a later phase.

   3. OUTPUT: Write the proposals YAML to the output_path above using the schema documented in the atomization-proposer agent definition.

   Terminal status:
   - STATUS: DONE with the output file written.
   - STATUS: NEEDS_CONTEXT if the window cannot be atomized (too short, no claims).
   ```

1. After the dispatch returns, Read `.mz/task/<task_name>/proposals_window_<wave_offset>.md` and validate structurally: YAML parses, `proposals:` list present, every proposal has `title`, `summary`, `draft`, and every draft's frontmatter block contains `type: research`, `source_type: research-report`, `report_path`, `status: draft`.

1. Update `state.md`: increment `wave_offset` to `<wave_offset + 1>`, append this window's output path to `WindowProposalPaths:` (YAML list).

1. Continue to the next window. **Dispatches are sequential, never parallel.** `atomization-proposer` is a single stateful agent instance with a 500-word input cap; sequential windows with 450-word budgets guarantee every dispatch returns `STATUS: DONE` without partial processing.

If any window returns `STATUS: NEEDS_CONTEXT`, record the window index under `state.md` `SkippedWindows:` and continue with the next window — do not abort the whole run for one empty window.

## Step 2: Merge per-window proposals

After `wave_offset` equals `AtomizationWindows`, merge every file listed under `WindowProposalPaths` into a single `.mz/task/<task_name>/proposals.md`:

1. Read each per-window file and concatenate its `proposals:` entries into a combined list.
1. If the combined list exceeds `MAX_NOTES` (15), dedupe by title similarity:
   - Normalize each title (lowercase, strip punctuation, collapse whitespace).
   - For pairs with identical normalized titles, keep the longer-body draft and drop the shorter one.
   - If titles are merely near-duplicates (e.g., Jaccard overlap >0.8 on normalized word sets), flag both for the user in `proposals.md` under a `possible_duplicates:` list and keep both until Phase 2.5 feedback resolves them.
1. After dedupe, if the count still exceeds `MAX_NOTES`, truncate to the first 15 entries in window order. Record `TruncatedProposals: <dropped count>` in `state.md` and add a top-level `truncation_warning:` key to `proposals.md` naming the dropped titles so Phase 2.5 makes the loss visible.
1. Add a `proposal_count:` top-level key and a `source_windows:` top-level list recording which window each surviving proposal came from — the user needs this to give per-window feedback in Phase 2.5.

Update `state.md`: `Phase: 2_atomized`, `Status: proposals_ready`, `ProposalsPath: .mz/task/<task_name>/proposals.md`, `ProposalCount: <N>`.

## Step 3: Return to Phase 2.5

Hand control back to `SKILL.md` Phase 2.5. The gate reads `proposals.md` verbatim and presents it to the user via AskUserQuestion. Do not present proposals from inside this phase file.

Gate outcomes:

- `approve` → continue to Step 4 (post-approval write).
- `reject` → update `state.md` Status to `aborted_by_user`, halt. No vault writes have occurred.
- Feedback or per-proposal skip numbers → re-dispatch the affected window(s) only (if feedback targets specific atomization windows), or filter the proposal list by the skip numbers, regenerate `proposals.md`, and re-present via Phase 2.5. Repeat until explicit approval.

## Step 4: Post-approval write to vault

This step runs only after Phase 2.5 returns `approve`.

1. Read vault CLAUDE.md (cached from Phase 0) to reconfirm the permanent folder convention stored under `PermanentFolder` in `state.md`.

1. Ensure the `research/` subfolder exists inside the permanent folder: `<Vault>/<PermanentFolder>/research/`. If missing, create it. Record `ResearchFolderCreated: true` in `state.md` when applicable.

1. Filter `proposals.md` by the Phase 2.5 decision (all proposals if `approve`, subset if numbers were skipped).

1. For each approved proposal, derive the vault filename:

   - Lowercase the claim title.
   - Replace whitespace with hyphens.
   - Strip any character outside `[a-z0-9-]`.
   - Collapse consecutive hyphens to one.
   - Truncate to 60 characters, trim trailing hyphens.
   - Append `.md`.
   - If the resulting filename collides with an existing file under `<Vault>/<PermanentFolder>/research/`, append `-2`, `-3`, ... before `.md` until the path is free.

1. Build the written note content by taking the draft body from the proposal and guaranteeing the mandatory frontmatter keys are present:

   ```yaml
   title: "<claim-style title>"
   created: <today's YYYY-MM-DD>
   type: research
   source_type: research-report
   report_path: "<ReportPath>"
   source: "<ReportPath>"
   tags: []
   status: draft
   ```

   If the agent's draft already has any of these keys with different values, overwrite with the values above — they are load-bearing for downstream search and linkage. Preserve any additional frontmatter keys the agent inferred from vault CLAUDE.md conventions (e.g., extra tags).

1. Write each note to `<Vault>/<PermanentFolder>/research/<filename>.md` using the `Write` tool.

1. Re-read every written file and verify:

   - The frontmatter block parses.
   - All five mandatory research keys are present: `type: research`, `source_type: research-report`, `report_path`, `status: draft`, `source`.
   - The body matches the draft body from the approved proposal.

1. Append each written path and title-to-path mapping to `state.md`:

   - `FilesWritten:` (YAML list of absolute paths).
   - `TitleToPath:` (YAML mapping of claim title → absolute path). The link-suggester dispatch in Step 5 needs this.

Update `state.md`: `Phase: 2_written`, `Status: notes_written`, `NotesWritten: <N>`.

## Step 5: Dispatch link-suggester

Dispatch the `link-suggester` agent (model: sonnet) with the prompt below. This agent scans the vault for existing notes that each written note should reference via `[[wikilinks]]`.

```
New notes written (title → path mapping):
<paste TitleToPath block from state.md as YAML>

Vault root: <Vault from state.md>
Task dir: .mz/task/<task_name>/

Your task:

For each new note, scan the vault for existing notes that the new note should reference via [[wikilinks]]. For every candidate target, record:
- Source note title (one of the new notes)
- Target note title (existing vault note)
- Relationship type, chosen from: supports | contradicts | extends | example-of | prerequisite-for | see-also
- One-sentence reason grounded in the actual content of both notes — not a guess

Caps:
- At most 5 link suggestions per new note.
- Do not propose links between two new notes at this stage.
- Skip candidates whose relationship you cannot justify in one sentence from read content.

Write proposals to `.mz/task/<task_name>/link_suggestions.md` using the YAML shape documented in the link-suggester agent definition (links list with source_title, source_path, targets).

Terminal status:
- STATUS: DONE with the file written.
- STATUS: DONE_WITH_CONCERNS if the vault has fewer than 10 readable notes.
- STATUS: NEEDS_CONTEXT only if the vault root is missing or unreadable.
```

After the agent returns, Read `.mz/task/<task_name>/link_suggestions.md` and validate structure. Update `state.md`: `Phase: 3_links_ready`, `Status: link_suggestions_ready`, `LinkSuggestionsPath: .mz/task/<task_name>/link_suggestions.md`.

## Step 6: Return to Phase 3.5

Hand control back to `SKILL.md` Phase 3.5. The gate reads `link_suggestions.md` verbatim and presents it to the user via AskUserQuestion. Do not present link suggestions from inside this phase file.

Gate outcomes:

- `approve` → continue to Step 7 (apply).
- `reject` → update `state.md` Status to `complete` with `LinksAdded: 0`, `LinksSkipped: true`. Written notes stay on disk without a Related section.
- Feedback or per-link skip titles → filter the proposals list, re-present via Phase 3.5. Repeat until explicit approval.

## Step 7: Apply approved links

After Phase 3.5 returns `approve` (with optional per-link skips), apply approved links to the already-written notes:

1. Group approved targets by `source_path`.
1. For each source note:
   - Read the note file.
   - If the body already contains a `## Related` section, append new `- [[Target Title]] — <relationship>` lines below it, preserving existing links.
   - If no `## Related` section exists, append one to the end of the body with a blank line before the header.
   - Preserve the frontmatter block untouched. Never move or rewrite existing content — only append to the Related section.
1. Re-read each modified note and verify the `## Related` section contains the expected lines. If verification fails, record `LinkApplyError: <path>` in `state.md` and halt — do not silently miss links.

## Step 8: Finalize state

After the last link write, update `state.md` to terminal:

```yaml
Status: complete
Phase: 3_complete
Completed: <ISO timestamp>
NotesWritten: <N>
LinksAdded: <N>
WindowsProcessed: <AtomizationWindows>
ReportPath: <absolute path>
Vault: <absolute path>
PermanentFolder: <folder>
```

Print the final orchestrator block (this is the Verification output for the skill):

```
vault-research complete:
  Report: <ReportPath>
  Windows processed: <AtomizationWindows>
  Notes written: <N>
  Location: <Vault>/<PermanentFolder>/research/
  Links added: <N>
  Status: draft (promote to evergreen when reviewed)
  Task dir: .mz/task/<task_name>/
```

## Error handling

- **An atomization window dispatch returns `DONE_WITH_CONCERNS`** → the window was over the 500-word cap. Record `Phase2WindowOverflow: <index>` in `state.md` and halt with an escalation via AskUserQuestion. The windowing in Phase 1 should have prevented this — investigate why the 450-word budget leaked.
- **File-write verification fails in Step 4.7** → halt immediately, record `Phase2WriteError: <path>` in `state.md`, escalate via AskUserQuestion. Do not proceed to link suggestions with missing notes.
- **`link-suggester` returns `NEEDS_CONTEXT`** → the vault root is unreachable. Record `Phase3VaultError` in `state.md` and finalize with `LinksAdded: 0` — the notes are already written and usable without links.
- **Drift detected in Step 7** (a target note in `link_suggestions.md` no longer exists) → skip that link, record `DriftedLinkTargets:` in `state.md`, continue with the surviving links.

## Common Rationalizations

| Rationalization                                                                              | Rebuttal                                                                                                                                                                                                 |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Dispatch windows in parallel — the output filenames are numbered so there is no collision." | "`atomization-proposer` is a single stateful agent; parallel dispatches share context and produce interleaved, lower-quality output. File-level non-collision is not the constraint — agent context is." |
| "Skip link suggestions for research notes — they link to each other anyway."                 | "Link suggestions surface connections to pre-existing vault notes outside the report; skipping impoverishes the knowledge graph and leaves research as a disconnected silo."                             |
| "Merge all per-window proposals with a simple concat — dedupe is overkill."                  | "Adjacent windows often produce twin proposals at section seams. A concat-only merge ships duplicate notes to the user and blows through `MAX_NOTES` without ever triggering truncation reasoning."      |
