# Phase 2: Back-fill Sources and Epistemic Status

## Goal

Translate the approved `claims_analysis.md` into a single frontmatter patch on the note: add or update `epistemic_status:` (aggregated across claims) and `sources:` (merged from claim-level proposals). Body content is preserved verbatim unless the user has explicitly opted into annotation mode during the Phase 1.5 feedback loop.

## Preconditions

Phase 1.5 has returned `approve`. The task state carries:

- `NotePath` — absolute path to the vault note under audit.
- `ClaimsAnalysisPath` — absolute path to the approved classification artifact.
- `AnnotationMode` — `true` if the user explicitly opted into inline body annotations during the Phase 1.5 feedback loop; otherwise `false` (the default). If the flag is absent from `state.md`, treat it as `false`.

Constants in use from `SKILL.md`:

- `EPISTEMIC_VOCAB`: `[first-hand, cited, inferred, received, unmarked]` — closed set.
- `TASK_DIR`: `.mz/task/` — root of the task workspace.

## Step 1: Derive the per-note aggregate `epistemic_status:`

### 1.1 Count classifications

Read `.mz/task/<task_name>/claims_analysis.md`. Tally the number of claims per `proposed_status` bucket from `summary.by_status`. If the tallies do not sum to `summary.total`, halt and escalate via AskUserQuestion — a drifted artifact cannot be aggregated.

### 1.2 Apply the 60% majority rule

Let `N = summary.total` and let `M` be the largest per-status count. If `M / N >= 0.60`, the aggregate `epistemic_status:` is the majority status. Otherwise the aggregate is the literal string `mixed` and the note body receives a one-line HTML comment (see Step 1.3).

Do not lower the threshold — 40% allows a minority classification to dominate; 60% ensures the aggregate reflects the actual distribution.

### 1.3 Handle the `mixed` case

When the aggregate is `mixed`, append a single HTML comment to the body of the note **immediately after the closing `---` of the frontmatter** (so the body text itself is untouched):

```html
<!-- epistemic: mixed distribution — see claims_analysis.md -->
```

This comment is the only body edit made when annotation mode is disabled. It is a pointer, not an annotation on prose.

## Step 2: Build the merged `sources: []` list

### 2.1 Collect per-claim sources

Iterate every entry in `claims:` and collect the strings in `proposed_sources`. Flatten into a single list preserving first-occurrence order across the traversal.

### 2.2 Dedupe

Remove exact-duplicate strings (case-sensitive match). URLs and titles that differ only by trailing slash or URL fragment count as separate entries — do not normalise beyond exact-match dedup; the user reviewed the list verbatim during Phase 1.5.

### 2.3 Preserve first-occurrence order

The final `sources:` list preserves the first-occurrence index from Step 2.1 after dedup. Do not alphabetise — order communicates narrative priority.

## Step 3: Patch the note's frontmatter

### 3.1 Read the note

Use the Read tool on `NotePath`. Capture:

- The frontmatter block — content between the first two `---` delimiters at the top of the file.
- The body — every character after the closing `---` of the frontmatter.

If the file does not start with `---`, halt and escalate via AskUserQuestion: "The note at `<path>` has no YAML frontmatter. Provenance frontmatter requires a frontmatter block. Create one, or abort?" Never fabricate a frontmatter block without user approval.

### 3.2 Apply the patch

Add or update these two keys in the frontmatter block:

- `epistemic_status: <aggregate from Step 1>`
- `sources: [<merged list from Step 2>]`

Preserve every other frontmatter key verbatim. Preserve key ordering where feasible (add new keys at the end of the block). Never modify or remove keys the skill did not author.

### 3.3 Write the file

Construct the new file content: the patched frontmatter block wrapped in its `---` delimiters, followed by the body captured in Step 3.1. The body remains EXACTLY as captured — no content changes, no whitespace normalisation, no reformatting.

Use the Write tool to save the file. Then Read the file back and confirm:

- The frontmatter block contains the new `epistemic_status:` and `sources:` keys.
- The body is byte-for-byte identical to what was captured in Step 3.1 (excluding the one-line HTML comment added in Step 1.3 when the aggregate is `mixed`).

If verification fails, halt and escalate via AskUserQuestion. Never assume a Write succeeded without the re-read confirmation.

## Step 4: Apply inline annotations (opt-in only)

This step runs ONLY if `AnnotationMode == true` in the task state. The default is `false` — frontmatter-only.

### 4.1 Locate each classified claim in the body

For every entry in `claims:`, use the `line_range` field to locate the claim in the note body. If the line range falls outside the current body (e.g., the body shifted between Phase 1 and Phase 2), skip that claim and log the miss in `.mz/task/<task_name>/annotation_log.md`.

### 4.2 Insert the annotation

Immediately after the final punctuation of the sentence containing the claim, insert:

```html
<!-- epistemic: <status> -->
```

Where `<status>` is the approved `proposed_status` for that claim. Do not modify the sentence itself. Do not insert on lines that already contain an `<!-- epistemic:` comment (idempotency).

### 4.3 Re-read and verify

Read the file after every annotation batch and confirm the note body still parses as valid Markdown (no broken list nesting, no unclosed fences). If verification fails, halt and point the user to `.mz/task/<task_name>/rollback` (the pre-edit capture from Step 3.1) via AskUserQuestion.

## Step 5: Finalize state

Update `.mz/task/<task_name>/state.md`:

- `Status: complete`
- `Phase: 2`
- `Completed: <ISO timestamp>`
- `ClaimsClassified: <summary.total>`
- `FrontmatterPatched: true`
- `AnnotationMode: <true|false>`
- `AggregateStatus: <majority or mixed>`

Print to the user:

```
Provenance back-fill complete: <N> claims classified; frontmatter patched on <note basename>.
Aggregate epistemic_status: <value>. Annotation mode: <on|off>.
```

## Common Rationalizations

| Rationalization                                                     | Rebuttal                                                                                                                                                                                         |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Patch body annotations by default — they're more visible."         | "Inline annotations require opt-in; default is frontmatter-only to avoid corrupting formatted notes. Body mutation without explicit consent violates the skill's contract with the note author." |
| "60% majority is too strict — use 40%."                             | "40% allows a minority classification to dominate; 60% ensures the aggregate reflects the actual distribution. If no single status clears 60%, `mixed` is the honest label."                     |
| "Normalise the sources list — alphabetise and strip URL fragments." | "The user approved the list verbatim during Phase 1.5. Post-approval normalisation silently changes the artifact the user signed off on; order and exact form are load-bearing."                 |

## Red Flags

- Modifying the note body when `AnnotationMode` is `false` (the one exception is the single HTML comment appended immediately after the frontmatter when the aggregate is `mixed`).
- Skipping the post-write re-read — the Write tool silently reports success on unchanged files.
- Dropping or reordering existing frontmatter keys that the skill did not author.
- Alphabetising or URL-normalising the sources list after Phase 1.5 approval.
- Writing placeholders (e.g., `<NEEDS_VALUE>`) into the note — this skill has no placeholder contract; every value is resolved before Phase 2 begins.
