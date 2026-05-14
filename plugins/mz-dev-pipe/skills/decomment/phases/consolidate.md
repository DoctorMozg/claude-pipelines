# Phase 3 — Consolidate proposals into a single diff

Merge every per-file proposal artifact written in Phase 2 into a single aggregated edit set. Validate non-overlap. Produce a human-readable `diff.md` for the Phase 3.5 approval gate and a machine-readable `edits.json` for Phase 4 apply.

## Inputs

- `proposals/<slug>.md` files (Phase 2 output, one YAML proposal per file)
- `dispatch_plan.md` (Phase 2 dispatch ledger — file → proposal_path mapping)
- `state.md` with `Phase: 2_complete`

## Outputs

- `${task_dir}diff.md` — human-readable diff for the approval gate
- `${task_dir}edits.json` — machine-readable apply input
- `${task_dir}skipped.md` — NEEDS_CONTEXT / BLOCKED tables
- `${task_dir}apply_warnings.md` — overlapping-edit conflicts and malformed proposals

## Steps

### 1. Load every proposal

Glob `${proposals_dir}*.md` and Read every file. Parse each as YAML. Expected proposer schema:

```yaml
schema_version: 1
file: <absolute path>
edits:
  - id: e1
    line_start: <int>
    line_end: <int>
    category: A|B|C|D|E|F
    rationale: <one-line reason>
    old_string: <verbatim bytes>
    new_string: <verbatim bytes>
status: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
context_request: <only when status is NEEDS_CONTEXT>
block_reason: <only when status is BLOCKED>
```

Validate `schema_version: 1`. If a proposal is malformed (parse failure, missing required keys, wrong schema_version), append a row to `apply_warnings.md` under the malformed-proposals table and skip it. Do not abort the phase.

### 2. Partition by status

- `DONE` / `DONE_WITH_CONCERNS` — proposal contributes to the consolidated edit set.
- `NEEDS_CONTEXT` — record in `skipped.md` under the NEEDS_CONTEXT section. Do not include its edits.
- `BLOCKED` — record in `skipped.md` under the BLOCKED section. Do not include its edits.

A `DONE` proposal with an empty `edits:` list is valid (no AI artifacts found in that file) — count it as DONE, contribute zero edits.

### 3. Build the edit set

Iterate every contributing proposal in dispatch order. For each edit in the proposal's `edits[]` array, assign a global sequential id `e<N>` (`e1`, `e2`, ... across all files combined) and collect into a single edit list with these fields:

- `id` — `e1`, `e2`, ...
- `file_path` — absolute path (verbatim from proposal `file:`)
- `category` — A | B | C | D | E | F
- `rationale` — verbatim from proposer
- `line_start`, `line_end` — verbatim from proposer
- `old_string` — verbatim from proposer (full bytes, never truncated)
- `new_string` — verbatim from proposer (full bytes, never truncated)

Every `file_path` MUST be absolute. If a proposal carries a relative path, log to `apply_warnings.md` malformed table and drop the proposal entirely.

### 4. Overlap detection

Group edits by `file_path`. Within each group, sort by `line_start`. For every pair of edits in the same file where `[line_start_i, line_end_i]` and `[line_start_j, line_end_j]` overlap (any range intersection — shared endpoints count):

1. Append a row to `apply_warnings.md` overlap table with both edit ids, the file path, both line ranges, and both rationales.
1. Drop the edit with the higher global id (the later-discovered one) from the apply set.
1. Mark the surviving edit's `apply_status` as `kept_resolved_overlap` in the in-memory record (this annotation is for traceability; it does not change behavior in Phase 4).

Overlap detection is per-file, never global. Two edits on the same line range in different files are independent and both kept.

### 5. Write `edits.json`

Write to `${task_dir}edits.json`. Format as a single JSON object:

```json
{
  "schema_version": 1,
  "task_name": "<task_name>",
  "total_edits": <int>,
  "files_with_edits": <int>,
  "edits": [
    {
      "id": "e1",
      "file_path": "/abs/path/to/file.py",
      "category": "C",
      "rationale": "Restating-WHAT comment above single line of code.",
      "line_start": 42,
      "line_end": 42,
      "old_string": "    # increment counter\n    counter += 1\n",
      "new_string": "    counter += 1\n"
    }
  ]
}
```

The `edits` array contains every surviving edit after overlap resolution, ordered first by `file_path` (lexicographic) then by `line_start` ascending. `total_edits` equals the length of the array. `files_with_edits` equals the number of distinct `file_path` values in the array.

The `old_string` and `new_string` fields carry the FULL bytes from the proposer — never truncated. Truncation happens only in `diff.md` for display.

### 6. Write `diff.md`

Write to `${task_dir}diff.md`. One `##` section per file. Within each file, one `###` subsection per edit, ordered by `line_start` ascending.

Per-edit display: emit the old/new pair inside a fenced \`\`\`diff block. Truncate the displayed bytes to DIFF_DISPLAY_LINES_PER_EDIT lines max per side (old_string and new_string each capped independently). If a side exceeds DIFF_DISPLAY_LINES_PER_EDIT lines, emit the first DIFF_DISPLAY_LINES_PER_EDIT lines and append a literal line `... (truncated; full bytes in edits.json edit id <ID>)` directly below the truncated content, then close the fence.

Header structure:

````markdown
# Decomment — aggregated edit diff

**Task**: <task_name>
**Total edits**: <N> across <K> files
**Skipped files**: <S> (see skipped.md)

---

## src/auth/login.py

### e3 — category C: Restating-WHAT comment above single line of code

Lines 42–42

```diff
-    # increment counter
-    counter += 1
+    counter += 1
```

### e4 — category A: Section-banner divider over generic label

Lines 90–94

```diff
-# ==================
-# Helpers
-# ==================
-
-def _shape(x):
+def _shape(x):
```

---

## src/api/handlers.ts

### e7 — category B: Phase header above trivial init

Lines 12–13

```diff
-// Phase 1: Initialize
-const cache = new Map();
+const cache = new Map();
```
````

The truncation marker line is part of the fenced diff block (so the user sees it in the same visual region as the truncated bytes). The `<ID>` placeholder is the global edit id (e.g., `e7`).

### 7. Write `skipped.md`

Write to `${task_dir}skipped.md`. Two tables — NEEDS_CONTEXT first, BLOCKED second. If either table has zero rows, emit the header and the column row only (no data rows).

```markdown
# Skipped files

## NEEDS_CONTEXT

| file_path | proposer_request |
| --------- | ---------------- |

## BLOCKED

| file_path | reason |
| --------- | ------ |
```

The `proposer_request` column carries the verbatim `context_request` field from the proposal. The BLOCKED `reason` column carries the verbatim `block_reason` field.

### 8. Write `apply_warnings.md`

Write to `${task_dir}apply_warnings.md`. Two tables — overlapping edits first, malformed proposals second.

```markdown
# Apply warnings — pre-flight conflicts

## Overlapping edits (resolved by dropping later edit)

| kept_id | dropped_id | file | overlap_range | kept_rationale | dropped_rationale |
| ------- | ---------- | ---- | ------------- | -------------- | ----------------- |

## Malformed proposals (skipped)

| proposal_path | reason |
| ------------- | ------ |
```

`overlap_range` is formatted as `lines <kept.line_start>-<kept.line_end> vs <dropped.line_start>-<dropped.line_end>`. The `reason` column for malformed proposals names the specific failure mode (parse error, missing key, wrong schema_version, relative path).

### 9. Update `state.md`

Append/update these fields:

- `Phase: 3_complete`
- `files_with_edits: <K>` — distinct file count in `edits.json`
- `total_edits: <N>` — total edit count in `edits.json`
- `FilesWritten:` append `diff.md`, `edits.json`, `skipped.md`, `apply_warnings.md` to the existing list
- Next gate: `gate_diff_pending`

Emit a one-line visible summary to the chat:

```
Consolidation complete: <N> edits across <K> files. Gate incoming.
```

## Red Flags

- You let overlapping edits through to Phase 4 — the Edit tool will silently fail on the second match attempt because the first edit already consumed surrounding context. Per-file overlap detection is mandatory.
- You wrote `edits.json` with relative paths — Phase 4 needs absolute paths. Drop any proposal with a relative `file:` field.
- You included BLOCKED or NEEDS_CONTEXT proposals' edits in `edits.json` — those proposals contribute zero edits; only DONE and DONE_WITH_CONCERNS do.
- You truncated `old_string` inside `edits.json` — truncation is display-only and happens in `diff.md` only. The Phase 4 Edit calls need the full bytes to match.
- You sorted edits across files when overlap-detecting — overlap is per-file, never global. Lines on the same range in different files do not conflict.
- You dropped the earlier edit on overlap — the convention is to keep the lower-id (earlier-discovered) edit. The later one carries less context-priority.
- You aborted the phase on a single malformed proposal — record it in `apply_warnings.md` and continue. The rest of the proposals are valid work product.

## Verification

- Sum of `edits` array length in `edits.json` equals `total_edits` in `state.md`.
- Every `file_path` value in `edits.json` is absolute (begins with `/`).
- No two edits in `edits.json` for the same `file_path` have overlapping `[line_start, line_end]` ranges.
- Every BLOCKED proposal from Phase 2 appears in `skipped.md` BLOCKED table; every NEEDS_CONTEXT proposal appears in the NEEDS_CONTEXT table.
- `diff.md` has exactly one `## <file>` section per unique `file_path` in `edits.json`.
- Every `old_string` / `new_string` displayed in `diff.md` is either ≤ DIFF_DISPLAY_LINES_PER_EDIT lines OR truncated with the literal marker line referencing the matching edit id from `edits.json`.
- `state.md` `FilesWritten` lists all four phase artifacts after this phase exits.
