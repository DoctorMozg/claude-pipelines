# Phase 2 — Parallel Proposer Dispatch

Dispatches `batch-fix-proposer` (haiku) agents in waves of `MAX_PARALLEL` (6). Each proposer reads one file, applies the approved criteria, and writes a proposal artifact containing zero or more targeted edits.

## Contents

- [2.1 Build dispatch list](#21-build-dispatch-list)
- [2.2 Dispatch in waves](#22-dispatch-in-waves)
- [2.3 Collect proposals](#23-collect-proposals)
- [2.4 Retry NEEDS_CONTEXT once](#24-retry-needs_context-once)

______________________________________________________________________

## 2.1 Build dispatch list

Read `.mz/task/<task_name>/candidates.md`. Filter to rows tagged `likely_relevant` or `unclear`. Discard `likely_skip`. The result is the dispatch list.

For each file in the dispatch list, derive a file slug for the proposal artifact:

- Take the file path, replace `/` with `__`, strip the `.md` extension.
- Example: `plugins/mz-knowledge/skills/vault-health/SKILL.md` → `plugins__mz-knowledge__skills__vault-health__SKILL`.
- Proposal path: `.mz/task/<task_name>/proposals/<file_slug>.md`.

Write the full dispatch list to `.mz/task/<task_name>/dispatch_plan.md` for traceability. One row per file with columns: `wave`, `file_path`, `proposal_path`.

## 2.2 Dispatch in waves

Split the dispatch list into waves of at most `MAX_PARALLEL` (6) files each. For each wave, send a **single assistant message** containing 1–6 parallel `Agent(...)` tool calls with `subagent_type: "batch-fix-proposer"`.

Dispatch prompt template (one per file):

```
You are dispatched by the batch-fix skill. Task_name: <task_name>.

Inputs:
- file_path: <absolute path to the target file>
- criteria_path: .mz/task/<task_name>/criteria.md
- output_path: .mz/task/<task_name>/proposals/<file_slug>.md
- file_type: skill|phase|agent

Read the file. Read criteria.md. Apply the ladder in your agent body: for each criterion
whose applies_to matches this file_type, determine if the file already satisfies the check
(emit nothing) or fails the check (emit a {old_string, new_string, rationale} edit).

Emit zero or more edits. Do not rewrite content outside the scope of any criterion.
Follow the exact output schema in your agent definition. Emit exactly one STATUS line.
```

Never pass the contents of `criteria.md` inline — the proposer reads the file. Never pass the contents of the target file inline — the proposer reads it.

Wave execution rules:

- A wave is exactly one assistant message. The runtime parallelizes the Agent calls within that message; sequential messages are sequential.
- Wait for every agent in the current wave to return before starting the next wave.
- If the dispatch list has 13 files: wave 1 = 6, wave 2 = 6, wave 3 = 1.
- Never start a wave larger than 6. Never stagger agents within a wave.
- Never background a proposer (`run_in_background: true`) — proposers write artifacts and background mode silently drops writes.

## 2.3 Collect proposals

After each wave, record the returned STATUS and proposal path per agent. Update `state.md` after each wave:

- `Phase: 2_wave_<N>`
- `proposals_done: N`
- `proposals_done_no_change: N`
- `proposals_needs_context: N`
- `proposals_blocked: N`

Do not `Read` every proposal here — Phase 3 (consolidate) reads them in bulk. In this phase, only track the STATUS distribution.

## 2.4 Retry NEEDS_CONTEXT once

For every agent that emitted `STATUS: NEEDS_CONTEXT`, retry exactly once in a follow-up wave (still bounded by `MAX_PARALLEL`):

- Read the returned `NEEDS_CONTEXT` rationale (the agent should have written a `context_request` field in its proposal artifact).
- Update `criteria.md` with a clarifying `note` attached to the relevant criterion, or expand the `detect`/`fix` fields if ambiguous.
- Re-dispatch the same file with the updated criteria.

If the retry still returns `NEEDS_CONTEXT`, record the file in `.mz/task/<task_name>/skipped.md` with the context request and move on. Do not loop a third time.

`BLOCKED` results are never retried — they are recorded in `skipped.md` and surfaced in Gate 2.

### State update at phase exit

- `Phase: 2_complete`
- `waves_run: N`
- `proposals_done: N`
- `proposals_done_no_change: N`
- `proposals_skipped: N` (NEEDS_CONTEXT after retry + BLOCKED)

Emit a one-line visible summary:

```
Dispatch complete: <N> DONE, <N> DONE_NO_CHANGE, <N> skipped. Consolidating.
```
