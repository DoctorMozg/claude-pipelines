# Phase 2: Writing + Phase 3: Naturalize Pass

## Phase 2: Writing (expert-copywriter)

### 2.1 Prepare dispatch context

Compute the output path:

```
output_path = .mz/reports/<YYYY_MM_DD>_copywrite_<slug>.md
```

Use today's date with underscores. Slug derives from topic + format (snake_case, max 20 chars). On collision append `_v2`, `_v3`.

### 2.2 Dispatch expert-copywriter

Dispatch the agent with a compact, task-specific prompt. Do **not** repeat the agent's general instructions — the agent file is self-contained.

Dispatch prompt template:

```
Topic: <one-paragraph summary of what to promote>
Format: <landing | email | announcement | social | changelog | pitch>
Output path: <absolute or repo-relative path>
Source artifacts:
  - .mz/task/<task_name>/brief.md
  - @brief:<path>  (only if user passed @brief: modifier)
Audience: <copy from brief.md>
Value claim: <copy from brief.md>
Tone decisions: <copy three lines from brief.md>
Format-specific constraints: <copy from brief.md>
Signature vocabulary to preserve: <copy from brief.md codebase tone-match>
Evidence available: <named customers, numbers, behaviors from brief.md>
Open questions / gaps: <copy from brief.md — agent must NOT invent answers>
```

Dispatch as a single Agent tool call. Use `subagent_type: expert-copywriter`. Do not background the call — the orchestrator must wait for the result before Phase 3.

### 2.3 Validate the output

After the agent returns:

1. Verify the output file exists and is non-empty.
1. Verify the agent emitted `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`. On `BLOCKED` or `NEEDS_CONTEXT`, re-dispatch once with clarification; if it fails again, escalate to the user via AskUserQuestion.
1. Read the output file. Confirm:
   - Format matches the request (landing has hero+H2 sections; email has subject+body+CTA; etc.)
   - Value claim is present in the first sentence (BLUF)
   - Named customers/numbers in the brief appear in the copy (none invented)
   - CTAs are imperative and single-action
   - Word counts are within format constraints (e.g., social ≤280 chars)

If the file is malformed (wrong format shape, hallucinated metrics, missing CTA), escalate to the user. Do not auto-retry more than once.

Update `state.md`: phase → `writing_complete`, append output path to `FilesWritten`.

## Phase 3: Auto-naturalize Pass (expert-naturalizer)

This phase runs automatically after Phase 2. No approval gate. The naturalizer rewrites the copy in place to remove residual AI patterns from `expert-copywriter`'s output.

### 3.1 Prepare dispatch context

The output path from Phase 2 becomes both the input and the output for the naturalizer (in-place rewrite). The signature vocabulary from `brief.md` is passed as a preserve list — these are project voice anchors and must not be stripped.

### 3.2 Dispatch expert-naturalizer

Dispatch prompt template:

```
Mode: in-place rewrite
Input file: <output_path from Phase 2>
Output file: <same path — overwrite>
Severity: assume Medium AI (copywriter output typically has medium AI-pattern density)
Strategy: vocabulary swaps, em-dash reduction, mechanical-antithesis breakage, restore specific verbs in place of nominalizations, preserve all CTAs verbatim
Preserve list:
  - All CTAs (call-to-action text, button labels, link anchors)
  - All named customers, product names, version numbers, dates
  - All numbers and metrics
  - All URLs, file paths, email addresses
  - Project signature vocabulary: <copy from brief.md>
  - Format scaffolding (hero block, H2 headers, subject line, sign-off, etc.)
Word-count target: cut up to 10% if AI-pattern density is high; preserve if already lean. Promotional copy should not balloon.
Long-document handling: chunk by H2 sections only if total >2000 words (rare for copy)
Web research: no (use embedded vocabulary)
Format awareness: <landing | email | announcement | social | changelog | pitch> — naturalizer must not break the format's structural conventions
```

Dispatch as a single Agent tool call. `subagent_type: expert-naturalizer`. Wait for completion.

### 3.3 Validate the rewrite

After the agent returns:

1. Verify the output file still exists and is non-empty.
1. Read the output file. Confirm:
   - All CTAs preserved verbatim
   - All named customers, numbers, and metrics preserved
   - Format scaffolding intact (hero block, H2 headers, subject line, etc.)
   - Naturalization report appended at the bottom
   - Word count is in the expected range (no >15% delta from Phase 2 output)
1. Verify the naturalization report contains: delta word count, patterns broken, burstiness estimate, preserved terms.
1. If the agent emitted `STATUS: BLOCKED`, the original Phase 2 output is preserved (the naturalizer should not have overwritten on BLOCKED). Warn the user that naturalization did not run.

Update `state.md`: phase → `complete`, naturalize delta recorded.

## Final output

Emit the final verification block defined in SKILL.md → Verification:

```
Copywriting pipeline complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_copywrite_<slug>.md
Format:     <landing|email|announcement|social|changelog|pitch>
Naturalize: applied (<words removed>, <patterns broken>)
Files:
  - brief.md
  - <output>.md (post-naturalize)
```

If naturalization was skipped due to BLOCKED status, replace `Naturalize: applied (...)` with `Naturalize: skipped (<reason>)`.

## Error Handling within these phases

- `expert-copywriter` returns `BLOCKED` → re-dispatch with clarification once. If still blocked, escalate via AskUserQuestion: offer to write a partial draft or abort.
- `expert-copywriter` returns `NEEDS_CONTEXT` → read the agent's stated missing piece, fix in `brief.md` or dispatch prompt, re-dispatch.
- `expert-copywriter` invents metrics or customers not in the brief → reject the output, re-dispatch with `Evidence available` constraint repeated and an explicit "do not invent" instruction.
- `expert-naturalizer` returns `BLOCKED` → keep Phase 2 output as final, warn the user.
- `expert-naturalizer` returns `DONE_WITH_CONCERNS` → forward concerns to the user in the final verification block; do not auto-retry.
- Naturalizer breaks format scaffolding (e.g., strips H2 headers from a landing page) → restore from Phase 2 backup; log the regression as a `DONE_WITH_CONCERNS` note.
