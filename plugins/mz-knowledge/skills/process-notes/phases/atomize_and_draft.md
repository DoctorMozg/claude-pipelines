# Phase 1: Atomize and Draft

## Goal

Detect atomic note boundaries in the resolved input and draft complete note content for each proposed atomic note. Delegated to the `atomization-proposer` agent. On exit, this orchestrator reads the agent's written proposal file and returns to the Phase 1.5 approval gate in SKILL.md.

## Pre-dispatch checks

Before dispatching, run these gates and escalate rather than guess:

- If the resolved input contains fewer than `MIN_INPUT_WORDS` (100) words, the input is likely already atomic. Ask the user via AskUserQuestion whether to wrap the input as a single permanent note or to expand it first. Do not silently atomize short input into a single proposal.
- If the resolved input exceeds `MAX_INPUT_WORDS_PER_PASS` (2000) words, ask the user to split the input across multiple runs. Quality degrades when a single atomization pass spans very long text.
- Confirm `TASK_DIR/<task_name>/` exists on disk. Create it if missing.

## Dispatch atomization-proposer

Dispatch the `atomization-proposer` agent (model: opus) with the prompt below. Fill the placeholders from Phase 0 setup:

```
Input content:
<paste the resolved input content verbatim>

Source path (for frontmatter `source:` field):
<input note path, daily note path, or "pasted raw text">

Vault conventions (from CLAUDE.md):
<paste relevant conventions extracted in Phase 0, or "none found">

Your task:

1. DETECT BOUNDARIES: Identify atomic note boundaries in the input.
   - Each atomic note captures exactly one clear idea or claim.
   - When in doubt, split — err toward smaller, linked notes.
   - Cap each note at roughly 500 words of body content.
   - Cap the total number of proposals at 10. If the input would produce more, return STATUS: NEEDS_CONTEXT and ask the orchestrator to split the input first.

2. DRAFT EACH NOTE: For every detected atomic note, write full content:
   - Title: claim-style assertion under 70 characters (e.g., "Variable rewards drive habit persistence"). Not a bare topic ("Habits").
   - Frontmatter keys: title, created (YYYY-MM-DD), type: permanent, source: <source path or "pasted">, tags: [], status: draft.
   - Body: 150-400 words in the user's own words, self-contained, directly claiming what the title asserts.
   - Do NOT write wikilinks in the body — linking is a later phase.

3. OUTPUT: Write a single YAML file to `.mz/task/<task_name>/proposals.md` using exactly this shape:

proposals:
  - title: "First claim-style title"
    summary: "One sentence core idea"
    draft: |
      ---
      title: "First claim-style title"
      created: YYYY-MM-DD
      type: permanent
      source: "<source path>"
      tags: []
      status: draft
      ---

      Full note body here...

  - title: "Second claim-style title"
    summary: "..."
    draft: |
      ---
      ...

Follow vault CLAUDE.md conventions for tag taxonomy and any additional frontmatter fields — merge them into the frontmatter block, keep `status: draft` always.

Terminal status:
- STATUS: DONE with `proposals.md` written.
- STATUS: NEEDS_CONTEXT if input is too vague, too long, or would exceed 10 proposals — describe the blocker in one sentence.
```

## After the agent returns

1. Read `.mz/task/<task_name>/proposals.md`.
1. Validate structurally:
   - File parses as YAML with a `proposals:` list.
   - Every proposal has `title`, `summary`, and `draft`.
   - Every draft body has a frontmatter block containing `status: draft`.
   - No proposal title exceeds `MAX_TITLE_CHARS` (70).
   - Proposal count is ≤ `MAX_ATOMIC_NOTES_PER_RUN` (10).
1. If any validation fails, re-dispatch the agent once with a corrective note referencing the specific failure. If it still fails, escalate to the user via AskUserQuestion — do not proceed to the approval gate with malformed proposals.
1. Update `state.md`: `Phase: 1`, `Status: proposals_ready`, `ProposalsPath: .mz/task/<task_name>/proposals.md`, `ProposalCount: <N>`.
1. Return to SKILL.md Phase 1.5 with the proposal list formatted for the user-facing presentation.

## Constraints

- Never write notes to the vault in this phase. Phase 1 only produces a proposal file under `TASK_DIR/<task_name>/`.
- Never fabricate content beyond what the input supports. If the input is a single idea, it is fine to return a single proposal.
- Always pass the vault CLAUDE.md conventions into the agent dispatch so frontmatter schema and tag taxonomy match the vault.
