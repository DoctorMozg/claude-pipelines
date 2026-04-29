# Phase 2: Writing + Phase 3: Naturalize Pass

## Phase 2: Writing (expert-technical-writer)

### 2.1 Prepare dispatch context

Compute the output path:

```
output_path = .mz/reports/<YYYY_MM_DD>_document_<slug>.md
```

Use today's date with underscores. Slug derives from the brief (snake_case, max 20 chars). On collision append `_v2`, `_v3`.

### 2.2 Dispatch expert-technical-writer

Dispatch the agent with a compact, task-specific prompt. Do **not** repeat the agent's general instructions — the agent file is self-contained.

Dispatch prompt template:

```
Brief: <one-paragraph summary of what to document>
Diátaxis type(s): <e.g., reference, or tutorial+reference, or all>
Output path: <absolute or repo-relative path to write the document>
Source artifacts:
  - .mz/task/<task_name>/research.md
  - @doc:<path>  (only if user passed @doc: modifier)
Polish mode: <yes if @doc: provided, else no>
Word-count guidance: <e.g., 500–1500 for README, 1000–3000 for full reference>
Audience: <e.g., developers integrating the API, end users following a tutorial>
Constraints from research.md: <copy any hard constraints listed there>
```

Dispatch as a single Agent tool call. Use `subagent_type: expert-technical-writer`. Do not background the call — the orchestrator must wait for the result before Phase 3.

### 2.3 Validate the output

After the agent returns:

1. Verify the output file exists and is non-empty.
1. Verify the agent emitted `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`. On `BLOCKED` or `NEEDS_CONTEXT`, re-dispatch once with clarification; if it fails again, escalate to the user via AskUserQuestion.
1. Read the output file. Spot-check: does it have headers, code examples, and the requested Diátaxis structure?

If the file is malformed (no headers, no code blocks, wrong language), escalate to the user. Do not auto-retry more than once.

Update `state.md`: phase → `writing_complete`, append output path to `FilesWritten`.

## Phase 3: Auto-naturalize Pass (expert-naturalizer)

This phase runs automatically after Phase 2. No approval gate. The naturalizer rewrites the document in place to remove residual AI patterns from `expert-technical-writer`'s output.

### 3.1 Prepare dispatch context

The output path from Phase 2 becomes both the input and the output for the naturalizer (in-place rewrite).

### 3.2 Dispatch expert-naturalizer

Dispatch prompt template:

```
Mode: in-place rewrite
Input file: <output_path from Phase 2>
Output file: <same path — overwrite>
Preserve list:
  - All code blocks (fenced and inline)
  - All tables
  - All headers labeled with Diátaxis type tags ([Tutorial], [Reference], etc.)
  - All proper names from the codebase: <comma-separated list of API names from research.md public surface>
  - All version strings, file paths, URLs
  - Technical terms that may match the avoid list but are domain-specific (e.g., "robust" in security contexts, "leverage" in finance contexts) — mark `[PRESERVED: <term>]` only when non-obvious
Word-count target: cut up to 15% of word count if AI-pattern density is high; preserve if already lean
Long-document handling: chunk by H2 sections if total >2000 words
Web research: no (use embedded vocabulary)
```

Dispatch as a single Agent tool call. `subagent_type: expert-naturalizer`. Wait for completion.

### 3.3 Validate the rewrite

After the agent returns:

1. Verify the output file still exists and is non-empty.
1. Read the output file. Confirm it still contains the original code blocks, tables, headers, and named APIs.
1. Verify the naturalization report appended at the bottom of the file (delta word count, patterns broken, burstiness estimate, preserved terms).
1. If the agent emitted `STATUS: BLOCKED`, the original Phase 2 output is preserved (the naturalizer should not have overwritten on BLOCKED). Warn the user that naturalization did not run.

Update `state.md`: phase → `complete`, naturalize delta recorded.

## Final output

Emit the final verification block defined in SKILL.md → Verification:

```
Documentation pipeline complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_document_<slug>.md
Diátaxis:   <types from the document, e.g., tutorial+reference>
Naturalize: applied (<words removed>, <patterns broken>)
Files:
  - research.md
  - <output>.md (post-naturalize)
```

If naturalization was skipped due to BLOCKED status, replace `Naturalize: applied (...)` with `Naturalize: skipped (<reason>)`.

## Error Handling within these phases

- `expert-technical-writer` returns `BLOCKED` → re-dispatch with clarification once. If still blocked, escalate via AskUserQuestion: offer to write a partial doc or abort.
- `expert-technical-writer` returns `NEEDS_CONTEXT` → read the agent's stated missing piece, fix in research.md or dispatch prompt, re-dispatch.
- `expert-naturalizer` returns `BLOCKED` → keep Phase 2 output as final, warn the user.
- `expert-naturalizer` returns `DONE_WITH_CONCERNS` → forward concerns to the user in the final verification block; do not auto-retry.
