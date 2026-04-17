# Phase 3 — Consolidate Proposals

Reads every `proposals/*.md` written in Phase 2 and produces two artifacts: `diff.md` (human-readable review surface for Gate 2) and `edits.json` (machine-readable input to Phase 4 apply). Also surfaces `skipped.md` and `apply_warnings.md` for transparency.

## Contents

- [3.1 Read every proposal](#31-read-every-proposal)
- [3.2 Group and validate edits](#32-group-and-validate-edits)
- [3.3 Write diff.md](#33-write-diffmd)
- [3.4 Write edits.json](#34-write-editsjson)
- [3.5 Write skipped.md](#35-write-skippedmd)

______________________________________________________________________

## 3.1 Read every proposal

Glob `.mz/task/<task_name>/proposals/*.md` and Read every file. Parse each proposal as YAML. Expected schema per proposal (from the agent definition):

```yaml
file: <absolute path>
criteria_matched: [c1, c3]
edits:
  - id: e1
    old_string: "..."
    new_string: "..."
    rationale: "..."
status: DONE | DONE_NO_CHANGE | NEEDS_CONTEXT | BLOCKED
context_request: "<only when status is NEEDS_CONTEXT>"
block_reason: "<only when status is BLOCKED>"
```

A `DONE_NO_CHANGE` proposal has an empty `edits:` list — that is not an error.

## 3.2 Group and validate edits

Merge every edit across every proposal into a single in-memory list, keyed by absolute file path.

Per-file validation pass:

1. **No overlapping edits within a file.** If two edits have `old_string` values that overlap (one is a substring of the other, or they share a common prefix/suffix that would cause Edit to match ambiguously after the first apply), flag the conflict. Record in `apply_warnings.md` and drop the later edit from `edits.json` — but still show it in `diff.md` under a "conflicts" subsection so the user can re-trigger Gate 2 with feedback.
1. **Re-assign stable global ids.** Within a file, renumber edits as `<file_slug>.e1`, `<file_slug>.e2`, ... so Gate 2 feedback like "skip e3 in vault-review" is unambiguous.
1. **Preserve criterion attribution.** Each edit retains its source criterion id (from the proposer's `criteria_matched`) and rationale.

Cross-file consistency check:

- If the same `criteria_matched` id produced wildly different `new_string` values across files for the same failing pattern, that is a signal the proposers disagreed on interpretation. Flag in `apply_warnings.md` with both example outputs — do not silently pick one.

## 3.3 Write `diff.md`

Human-readable markdown. One `##` section per file that has at least one edit. Files that returned `DONE_NO_CHANGE` are not rendered here — they appear in the summary line only. Files that returned `BLOCKED` or `NEEDS_CONTEXT` (after retry) go in `skipped.md`.

Per-file section shape:

```
## plugins/mz-knowledge/skills/vault-health/SKILL.md

Criteria matched: c1, c3

### e1 — c1: <criterion check summary>

**Rationale**: <one-line rationale from the proposer>

~~~
- <old_string, first 40 lines of context max>
+ <new_string, first 40 lines of context max>
~~~

### e2 — c3: <criterion check summary>

...
```

If an edit's `old_string` is longer than 40 lines, truncate in the displayed diff but note `(old_string truncated for display — full body in edits.json)` so the user knows to inspect the machine-readable form if they need the exact bytes.

Append a per-file footer if there were conflicts:

```
### Conflicts (dropped from apply)

- e4 overlapped with e2; dropped. See apply_warnings.md for detail.
```

Top of file — summary block:

```
# Batch-Fix Diff

Task: <task_name>
Brief: <verbatim from state.md>

Files with edits: <N>
Total edits: <N>
Files DONE_NO_CHANGE: <N>
Files skipped (BLOCKED / NEEDS_CONTEXT): <N>

See skipped.md for skipped files; apply_warnings.md for conflicts.
```

## 3.4 Write `edits.json`

Machine-readable, consumed by Phase 4 apply. Schema:

```json
{
  "task_name": "<task_name>",
  "generated_at": "<ISO timestamp>",
  "files": [
    {
      "path": "<absolute path>",
      "criteria_matched": ["c1", "c3"],
      "edits": [
        {
          "id": "<file_slug>.e1",
          "criterion": "c1",
          "old_string": "<verbatim bytes>",
          "new_string": "<verbatim bytes>",
          "rationale": "<proposer rationale>"
        }
      ]
    }
  ]
}
```

Apply order within a file: first-to-last as listed. Apply order across files: any order — files are independent.

## 3.5 Write `skipped.md`

One table per skip reason:

```
## NEEDS_CONTEXT (after retry)

| file | context_request |
| ---- | --------------- |
| ...  | ...             |

## BLOCKED

| file | block_reason |
| ---- | ------------ |
| ...  | ...          |
```

If both lists are empty, write `No files were skipped in this run.` and move on.

### State update at phase exit

- `Phase: 3_complete`
- `files_with_edits: N`
- `total_edits: N`
- `conflicts_dropped: N`

Emit a one-line visible summary:

```
Consolidation complete: <N> files with <N> edits. Gate 2 incoming.
```
