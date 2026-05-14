# Phase 2 — Dispatch proposers in parallel waves

## Inputs

- `candidates.md` (Phase 1 output)
- `state.md` (`Phase: 1_complete`)

## Outputs

- `.mz/task/<task_name>/dispatch_plan.md` — wave / file_path / proposal_path / status table
- `.mz/task/<task_name>/proposals/<slug>.md` — one proposal artifact per dispatched file

## Steps

### 1. Build dispatch plan

Read `candidates.md`. For each candidate row (1-indexed), compute:

- `wave = ceil(index / MAX_PARALLEL)` — wave 1 holds rows 1..MAX_PARALLEL, wave 2 holds rows (MAX_PARALLEL+1)..(2×MAX_PARALLEL), and so on.
- `proposal_path = .mz/task/<task_name>/proposals/<filename-slug>.md` where `filename-slug` is the candidate's path with directory separators (`/`) replaced by `__` and the file extension preserved (e.g., `src/auth/login.py` → `src__auth__login.py`).

Write `dispatch_plan.md` as a markdown table:

```markdown
# Decomment dispatch plan

| wave | file_path | proposal_path | status |
|------|-----------|---------------|--------|
| 1 | <abs path> | .mz/task/<task_name>/proposals/<slug>.md | pending |
```

Initial `status` for every row is `pending`. The orchestrator updates this column in place after each wave completes.

### 2. Dispatch waves

For each wave in ascending order:

1. Update `state.md`: `Phase: 2_wave_<N>`.
1. In a single assistant message, dispatch up to `MAX_PARALLEL` (=6) `pipeline-decomment-proposer` agents in parallel — one Agent tool call per file in the wave. Each dispatch prompt must include:
   - The target file path (absolute).
   - The proposal output path (absolute, matching `proposal_path` for the row).
   - The `task_dir` path.
   - The reference table path: `plugins/mz-dev-pipe/skills/decomment/references/per-language-comment-syntax.md`.
   - The reminder line: `Read the reference table for your file's extension before tokenizing. Emit exactly one STATUS: line at end.`
1. Wait for every agent in the current wave to return before launching the next wave. Sequential messages are sequential — a wave is exactly one assistant message with N parallel Agent calls.
1. Never background a proposer (`run_in_background: true`). Proposers write proposal artifacts; background mode silently drops writes.
1. Never dispatch more than `MAX_PARALLEL` agents in one wave — split overflow into the next sequential wave.

For each agent's terminal `STATUS:` line, update the row's `status` column in `dispatch_plan.md`:

- `DONE` → `done`
- `DONE_WITH_CONCERNS` → `done_concerns` (log the agent's `## Concerns` block to `state.md` under `## Concerns`)
- `NEEDS_CONTEXT` → re-dispatch the same file exactly once in a follow-up wave, with the requested context (read the agent's `## Required Context` block from the proposal artifact and include it verbatim in the new prompt). If the retry still returns `NEEDS_CONTEXT`, escalate the row to `blocked`.
- `BLOCKED` → `blocked`. Never auto-retry on BLOCKED — record the `## Blocker` block in `skipped.md` and continue.

After each wave, update `state.md` counters:

- Increment `proposals_done` for rows landing on `done` or `done_concerns`.
- Increment `proposals_skipped` for rows landing on `blocked`.

### 3. Handle blocked files

For any row with final `status: blocked`, write a stub proposal artifact at the row's `proposal_path` so Phase 3 (consolidate) can iterate over a uniform proposal set:

```yaml
---
schema_version: 1
file_path: <abs path>
proposer: pipeline-decomment-proposer
status: BLOCKED
concerns: [<agent's blocker reason, verbatim from the ## Blocker block>]
edits: []
skipped: []
---
STATUS: BLOCKED
```

Also append a row to `.mz/task/<task_name>/skipped.md` (create the file if missing) with columns `file_path | reason | status`.

### 4. Update state.md

When all waves are complete:

- `Phase: 2_complete`
- `FilesWritten: [..., dispatch_plan.md, proposals/*.md]`
- `proposals_done: <count of done + done_concerns>`
- `proposals_skipped: <count of blocked>`

Emit a one-line chat summary before returning to the orchestrator for Phase 3:

```
Dispatch complete: <N> DONE, <N> DONE_WITH_CONCERNS, <N> blocked. Consolidating.
```

## Red Flags

- You dispatched more than `MAX_PARALLEL` (=6) agents in a single message — the cap belongs to the orchestrator; the agents themselves do not enforce it.
- You backgrounded any writer agent (proposers write proposal artifacts — they must complete in-foreground per the wave protocol).
- You retried a `BLOCKED` proposer agent — BLOCKED is terminal and never auto-retried.
- You retried a `NEEDS_CONTEXT` proposer more than once — escalate to `blocked` on the second attempt rather than looping a third time.
- You forgot to set `state.md` → `Phase: 2_complete` before Phase 3 starts — consolidation runs against a stale phase marker.
- You passed `criteria.md` or target-file contents inline in the dispatch prompt — proposers read these themselves; inlining wastes input tokens and breaks the agent's own context discipline.

## Verification

- Every row in `dispatch_plan.md` has a terminal `status` value (`done`, `done_concerns`, or `blocked`) — no `pending` rows remain.
- The `proposals/` directory contains one file per row in `dispatch_plan.md` (including stubs for `blocked` rows).
- `proposals_done + proposals_skipped == total candidate count` from Phase 1.
- `skipped.md` lists every row that ended in `blocked` with its reason.
- No `BLOCKED` row has a retry recorded in `dispatch_plan.md` history.
