# Phase 1: Search + Synthesize

## Goal

Dispatch `vault-query-answerer` to produce an answer with inline `[[wikilink]]` citations, a `## Sources` list, and an explicit `## Unknowns` list. Enforce a minimum citation density before returning the answer to the user.

## Step 1: Dispatch `vault-query-answerer`

Dispatch the `vault-query-answerer` agent (model: sonnet) with this task-specific prompt:

```
Question: "<verbatim question from state.md>"
Vault path: <vault_path>
Output path: .mz/task/<task_name>/answer.md
Task dir: .mz/task/<task_name>/

Parameters:
  max_notes: 20
  max_preview_words: 300
  citation_density_min_ratio: 0.02

Your task:

Answer the question using only vault content. Every factual claim must cite a vault note via inline [[wikilink]]. Maintain an explicit ## Unknowns section listing aspects of the question the vault does not support — an empty list is valid and informative.

Steps:

1. Extract anchor keywords from the question (key nouns, concepts, named entities).
2. Grep the vault for each anchor across filenames and note bodies (exclude .obsidian/).
3. Rank found notes by match density. Take top 20.
4. For each selected note, read the first 300 words.
5. Synthesize the answer:
   - Every factual claim gets an inline [[wikilink]] pointing to a note actually in the read set.
   - Collect all cited note paths for the ## Sources section.
   - List aspects not covered by any read note in ## Unknowns.
6. Write the artifact to output_path in the exact structure below.

Output structure:

# Answer

<prose with inline [[wikilink]] citations after each factual claim>

## Sources

- [[Note Title]] — <absolute path>
- ...

## Unknowns

- <aspect of question not covered by vault>
- ... (empty list is valid if the vault fully covers the question)

Terminal status:
- STATUS: DONE — artifact written, citations grounded in read set.
- STATUS: DONE_WITH_CONCERNS — vault has fewer than 10 readable notes, or zero relevant notes found.
- STATUS: NEEDS_CONTEXT — question or vault_path missing.
- STATUS: BLOCKED — vault unreadable.
```

## Step 2: Validate artifact structure

After the agent returns:

1. Read `.mz/task/<task_name>/answer.md`.
1. Verify the file contains all three required sections:
   - A `# Answer` heading followed by prose.
   - A `## Sources` heading.
   - A `## Unknowns` heading (even if the list beneath it is empty).
1. If any required section is missing, retry the dispatch once with an explicit reminder of the exact output structure. If still malformed after the retry, proceed to Step 4 with a DONE_WITH_CONCERNS note.

## Step 3: Citation density check

Count occurrences of `[[...]]` in the `# Answer` prose section only (exclude `## Sources` and `## Unknowns` — those aren't inline citations). Divide by the word count of the prose in that section.

If the resulting ratio is below `CITATION_DENSITY_MIN_RATIO` (0.02):

1. Re-dispatch `vault-query-answerer` once with an added instruction:

   > Your previous answer has too few inline citations (density `<measured>`, required `0.02`). Ensure at least 1 `[[wikilink]]` per 50 words of prose. Every factual claim must be grounded in a cited vault note. Do not invent links — every `[[wikilink]]` must resolve to a note actually in the read set. Re-write `answer.md` at the same output path.

1. Re-read `answer.md` and re-measure the ratio.

1. Only re-dispatch once. If the ratio is still below threshold after the second attempt, proceed to Step 4 and flag the shortfall in Step 5 with a DONE_WITH_CONCERNS note.

## Step 4: Return to user

Read `.mz/task/<task_name>/answer.md` and present the full text verbatim to the user. Do not summarize. Do not return a file path. Do not truncate. The user sees the complete answer body, the `## Sources` list, and the `## Unknowns` list exactly as the agent wrote them.

## Step 5: Update state

Update `.mz/task/<task_name>/state.md` with:

- `Status: complete`
- `Phase: 1`
- `Completed: <ISO timestamp>`
- `CitationCount: <N>` — number of `[[wikilink]]` occurrences in the `# Answer` prose.
- `CitationDensity: <0.NN>` — ratio of citations to prose words.
- `SourcesCount: <N>` — entries under `## Sources`.
- `UnknownsCount: <N>` — entries under `## Unknowns`.

If the citation density remained below threshold after the retry in Step 3, append `Concern: citation density <measured> below required 0.02 after retry`.

## Red Flags

- Re-dispatching the agent more than once for citation density — the retry is capped at one attempt, then proceed with a concern.
- Presenting a file path instead of the answer text — the user must see the full answer body verbatim.
- Skipping the citation density check and always proceeding — the check is load-bearing, not decoration.
- Returning a summary of the answer instead of the full verbatim text.
- Writing to any vault file — this skill is read-only on the vault.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-answer verification:
  [ ] answer.md contains # Answer, ## Sources, ## Unknowns sections
  [ ] Citation density measured and logged in state.md
  [ ] Full answer body presented verbatim to the user (not a path, not a summary)
  [ ] state.md Status is `complete` with Completed timestamp
  [ ] No vault files were modified by this skill
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## Error Handling

- **Agent STATUS: NEEDS_CONTEXT** → forward the required-context list to the user via AskUserQuestion; do not fabricate the missing input.
- **Agent STATUS: BLOCKED (vault unreadable)** → surface the blocker to the user; do not retry silently.
- **Agent STATUS: DONE_WITH_CONCERNS (thin vault or zero relevant notes)** → still present the answer and `## Unknowns` verbatim; the thin-vault concern goes into the final state.md `Concern:` line.
- **`answer.md` missing after dispatch** → retry the dispatch once; if still missing, report the failure explicitly rather than claiming success.
