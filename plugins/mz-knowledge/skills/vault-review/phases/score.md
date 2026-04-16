# Phase 1: Score and Build Review Queue

## Goal

Build a composite-scored review queue. Dispatch `moc-gap-detector` in parallel so structural gap data is ready by the time the queue is presented.

## Step 1: Scan permanent notes

Glob all `.md` files in the vault's permanent notes folder. Typical layouts:

- `<vault>/04 - Permanent/**/*.md`
- `<vault>/permanent/**/*.md`
- `<vault>/notes/permanent/**/*.md`

If the vault has no explicit permanent-notes folder, glob `<vault>/**/*.md` excluding `daily/`, `templates/`, `attachments/`, `.obsidian/`, and any `archive/`-prefixed folders. Record the resolved glob in `state.md` under `ScannedGlob`.

For each note, collect:

- `last_reviewed` frontmatter (ISO date; absent → treat as never reviewed → use `NEVER_REVIEWED_DAYS` as `days_since_review`)
- `maturity` frontmatter (`seedling` | `sapling` | `tree` | `ancient-tree`; absent → `seedling`)
- Outlink count: count `[[...]]` patterns in the note body (exclude frontmatter)
- Inlink count: count other notes in the vault that contain `[[<this note name>]]`
- `created` frontmatter or file `ctime` as the fallback age signal

Write the raw scan data to `.mz/task/<task_name>/scan.md` as a YAML list so Phase 2 can read it back.

## Step 2: Dispatch `moc-gap-detector` (parallel)

Dispatch `moc-gap-detector` alongside scoring. The two operations are independent — run them in the same message as parallel tool calls so gap data is ready when the queue is presented.

Dispatch prompt:

```
vault_path: <vault_path>
output_path: .mz/task/<task_name>/moc_gaps.md
task_name: <task_name>

Scan the vault for topic clusters lacking Maps of Content. Write moc_gaps.md per your agent spec. Report the top 10 most significant gaps, largest clusters first.
```

After the agent returns, read `.mz/task/<task_name>/moc_gaps.md` and extract the gap count for the Phase 1.5 presentation.

## Step 3: Compute composite score

For each scanned note:

```
days_since_review = (today - last_reviewed) in days
                  = NEVER_REVIEWED_DAYS if last_reviewed is absent

orphan_penalty    = ORPHAN_PENALTY if outlinks == 0 else 0

maturity_weight   = { seedling: 3, sapling: 2, tree: 1, ancient-tree: 0 }[maturity]

score             = (days_since_review / 30) + orphan_penalty + maturity_weight
```

Cap `score` at `SCORE_CAP`. Sort all scored notes by `score` descending. Take the top N where N is the mode's queue size:

- `daily` → `QUEUE_SIZE_DAILY`
- `weekly` → `QUEUE_SIZE_WEEKLY`
- `monthly` → `QUEUE_SIZE_MONTHLY`
- `smart` → `QUEUE_SIZE_SMART`

## Step 4: Write queue to state

Write `.mz/task/<task_name>/review_queue.md` with this exact YAML shape:

```yaml
mode: smart|daily|weekly|monthly
generated_at: <ISO timestamp>
queue:
  - title: "Note Title"
    path: "<absolute path>"
    score: 8.5
    last_reviewed: "2026-01-01"     # or "never"
    maturity: seedling
    outlinks: 0
    inlinks: 2
    days_since_review: 105
    reason: "105 days since review, 0 outlinks, maturity: seedling"
```

The `reason` field must be a human-readable single sentence assembled from the components that pushed the score up — not the raw formula. The Phase 1.5 gate presents `reason` directly to the user.

Update `state.md`: `Status: queue_ready`, `Phase: 1`, `QueueSize: <N>`, `MocGaps: <gap count or 0>`.

Return to SKILL.md Phase 1.5 gate with the queue and the MOC gap summary.

## Error handling

- **Empty scan** (zero permanent notes globbed) → escalate via AskUserQuestion with the resolved glob so the user can correct the folder convention.
- **All notes lack `last_reviewed`** (fresh vault) → proceed with `NEVER_REVIEWED_DAYS` for every note; note the flat-score condition in `state.md`.
- **`moc-gap-detector` fails or returns empty** → retry once with a clarified prompt. If still empty, continue without gap data and note the fallback in `state.md` — the review session can proceed without MOC context.
