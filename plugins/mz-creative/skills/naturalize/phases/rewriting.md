# Phase 2: Rewriting + Phase 2.5: Optional File Update

## Phase 2: Rewriting (expert-naturalizer)

### 2.1 Prepare dispatch context

Compute the output path:

```
output_path = .mz/reports/<YYYY_MM_DD>_naturalize_<slug>.md
```

Use today's date with underscores. Slug from setup. On collision append `_v2`, `_v3`.

### 2.2 Dispatch expert-naturalizer

Compose a compact dispatch prompt. Do **not** repeat the agent's general instructions — the agent file is self-contained.

Dispatch prompt template:

```
Mode: standalone rewrite
Input file: .mz/task/<task_name>/input.md
Output file: <output_path>
Severity: <Light|Medium|Heavy AI from analysis.md>
Strategy: <copy the "Proposed rewriting strategy" section from analysis.md>
Preserve list:
  - All code blocks (fenced and inline)
  - All tables
  - Proper names: <comma-separated from analysis.md>
  - File paths, URLs, version strings
  - Domain-specific technical terms: <list from analysis.md>
Word-count target: <copy "Estimated word-count delta" from analysis.md>
Long-document handling: <chunk by H2 if word count > 2000, else single pass>
Web research: <yes|no — pass through user's research: flag>
```

Dispatch as a single Agent tool call. `subagent_type: expert-naturalizer`. Wait for completion.

### 2.3 Validate the rewrite

After the agent returns:

1. Verify the output file exists and is non-empty.
1. Verify the agent emitted `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`.
1. Read the output file. Confirm:
   - Original code blocks, tables, proper names preserved
   - Naturalization report appended at the bottom
   - Word count is in the expected range (±5% of target delta)
1. On `BLOCKED` or `NEEDS_CONTEXT`, escalate via AskUserQuestion.

Update `state.md`: phase → `rewrite_complete`, append output path to `FilesWritten`.

## Phase 2.5: Optional In-Place File Update Gate

This phase runs **only** when the original input came from `@file:<path>` (not from inline text). The user may want the rewritten text to overwrite the original file in place.

### 2.5.1 Decide whether to offer the gate

If `state.md` shows `InputSource: inline`, skip this phase entirely.

If `state.md` shows `InputSource: file:<path>`, proceed to the gate.

### 2.5.2 Pre-gate emit block

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read both the original file (the one referenced by `@file:`) and the rewritten output. Capture both word counts, the naturalization report, and a short diff summary (sample of changes).

Before invoking AskUserQuestion, emit a text block:

```
**File update offer**
Rewriting complete. The original file is unchanged on disk; the rewritten text is at .mz/reports/<...>. Optionally apply the rewrite to the original file in place.

- **Apply** → overwrite the original file with the rewritten text
- **Skip** → leave the original file unchanged; the report stays at .mz/reports/
- **Diff** → show a diff summary first, then ask again
```

### 2.5.3 Invoke AskUserQuestion

```
Apply the rewrite to the original file <path>?

Original word count: <N>
Rewritten word count: <N> (delta: <±N>%)
Patterns broken: <count>
Burstiness: <before> → <after>

The original file is at: <path>
The rewrite is at: <output_path>

Sample of changes (first 3):
- "<original snippet>" → "<rewritten snippet>"
- ...

Type **Apply** to overwrite the original, **Skip** to keep both files, or **Diff** to see a fuller diff first.
```

### 2.5.4 Response handling

- **"apply"** → write the rewritten content to the original file path. Update `state.md`: `FileUpdateApplied: yes`. Confirm with a one-line message: `Original file updated: <path>`.
- **"skip"** → leave the original file untouched. Update `state.md`: `FileUpdateApplied: no`. Confirm: `Original file unchanged. Rewrite available at <output_path>`.
- **"diff"** → show a fuller diff (use `diff -u <original> <output>` if available, else fall back to a simple side-by-side preview of differing paragraphs), then re-invoke AskUserQuestion with only Apply / Skip options.

This gate has no Reject — the rewrite already exists; the question is only whether to apply it in place.

## Final output

Emit the final verification block defined in SKILL.md → Verification:

```
Naturalization complete.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_naturalize_<slug>.md
Input:      <source> (<words>)
Output:     <words> (delta: <±N>%)
Patterns:   <count broken>
Burstiness: <before> → <after>
File update: <yes|no|n/a>
```

`File update: n/a` for inline-text inputs. `yes`/`no` for `@file:` inputs based on Phase 2.5 outcome.

## Error Handling within these phases

- `expert-naturalizer` returns `BLOCKED` → preserve original input untouched, escalate via AskUserQuestion.
- `expert-naturalizer` returns `NEEDS_CONTEXT` → re-dispatch once with the missing context (usually a clearer preserve list).
- File path from `@file:` becomes unwritable between Phase 0 and Phase 2.5 → warn the user, keep the report as the canonical artifact.
- Diff command unavailable → fall back to listing the first 5 differing paragraphs side-by-side.
