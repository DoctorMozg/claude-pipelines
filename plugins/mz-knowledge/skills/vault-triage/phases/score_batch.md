# Phase 1: Score Batch

## Goal

Dispatch the `triage-scorer` agent to apply heuristic rules to the batch of inbox notes resolved in Phase 0, producing a deterministic triage proposal at `.mz/task/<task_name>/triage_batch.md`. Validate the artifact shape before handing control back to SKILL Phase 1.5.

## Step 1: Assemble the note path list

1. Read `state.md` and extract `BatchPaths` — the absolute paths of the `BATCH_SIZE` inbox notes selected in Phase 0.
1. Build the ordered `note_paths` list (order preserved — indices in `triage_batch.md` become the override keys the user types in Phase 1.5).
1. If `BatchPaths` is empty or missing, fail fast — return to SKILL Phase 0 and re-run setup rather than dispatching the agent on an empty batch.

## Step 2: Dispatch `triage-scorer`

Dispatch the `triage-scorer` agent (model: haiku) with the prompt below. Fill placeholders from Phase 0 state.

```
Input:
  note_paths:
    - <absolute path 1>
    - <absolute path 2>
    - ...
  output_path: .mz/task/<task_name>/triage_batch.md
  task_name: <task_name>
  thresholds:
    FLEETING_AGE_DAYS_DEFER_THRESHOLD: 14
    STUB_WORD_THRESHOLD: 20

Your task:

1. For each note in note_paths, read the file, extract frontmatter and body,
   and compute: body_word_count, mtime_days_ago, outlink_count, has_status.
2. Apply the heuristic ladder from your agent definition (first matching rule wins).
3. Build a 40-character preview from the first non-frontmatter characters of the body.
4. Write triage_batch.md as YAML with shape:
     decisions:
       - path: "<absolute path>"
         title: "<note title>"
         preview: "<40-char preview>"
         proposed_decision: promote|merge|discard|defer
         proposed_merge_target: null
         rationale: "<one sentence>"
     summary:
       promote: N
       merge: N
       discard: N
       defer: N

Terminal status:
- STATUS: DONE — artifact written, every note scored.
- STATUS: DONE_WITH_CONCERNS — batch was empty (should not happen — the orchestrator pre-filters).
- STATUS: NEEDS_CONTEXT — note_paths or output_path missing from the dispatch prompt.
- STATUS: BLOCKED — the inbox folder is unreadable or an individual note read errored and is not recoverable.
```

## Step 3: Validate the artifact shape

After the agent returns, Read `.mz/task/<task_name>/triage_batch.md` and verify:

- The file exists and parses as a YAML document.
- A top-level `decisions:` list exists with one entry per note in the input batch (order preserved).
- Every entry contains the keys: `path`, `title`, `preview`, `proposed_decision`, `proposed_merge_target`, `rationale`.
- `proposed_decision` is one of: `promote`, `merge`, `discard`, `defer`.
- `proposed_merge_target` is literally `null` for every entry — the agent must not pre-select a merge target.
- A top-level `summary:` map exists with integer counts for `promote`, `merge`, `discard`, `defer`.

If any check fails, re-dispatch `triage-scorer` exactly once with an added instruction block in the prompt:

```
Previous output failed validation: <one-line reason — list the missing key, wrong decision value, or non-null merge target>.
Re-emit triage_batch.md in the exact YAML shape specified above. Do not substitute, paraphrase, or reorder keys.
```

If the second dispatch also fails validation, emit `STATUS: BLOCKED` with the validation failure details and do not advance.

## Step 4: Update state

Update `state.md`:

```
Phase: 1
Status: batch_scored
BatchArtifact: .mz/task/<task_name>/triage_batch.md
BatchSize: <actual entry count from decisions list>
ProposedCounts: promote=<N>, merge=<N>, discard=<N>, defer=<N>
```

## Step 5: Return to SKILL Phase 1.5

Hand control back to SKILL.md Phase 1.5. The orchestrator (not a subagent) then Reads `triage_batch.md` in full, formats the verbatim presentation, and invokes AskUserQuestion per the approval-gate structure in SKILL.md.

## Constraints

- Never mutate inbox notes in this phase. Phase 1 produces only `triage_batch.md` under `TASK_DIR/<task_name>/`.
- Never let the agent choose a merge target. `proposed_merge_target` must stay `null` for every entry; the user names the target in Phase 1.5.
- Never proceed to Phase 2 without the artifact shape validating on either the first or the re-dispatched attempt.
