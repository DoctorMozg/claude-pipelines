# Phase 3: Cleanup Execution

The orchestrator dispatches `expert-leftover-cleaner` (opus) in parallel waves to apply the approved cleanup plan from `detection.md`. Files are split into work units of ≤ MAX_FILES_PER_DISPATCH (25) files each; up to MAX_PARALLEL_AGENTS (6) cleaners run concurrently per wave. Output: edited files in-place plus `.mz/task/<task_name>/cleanup_wave_<N>.md` reports per wave.

## 3.1 Wave planning

1. **Compute waves** — split the file list from `detection.md` into chunks of MAX_FILES_PER_DISPATCH. Number of cleaner agents per wave = `min(MAX_PARALLEL_AGENTS, chunks_remaining)`.
2. **Group by category mix** — keep files with WHAT-not-WHY candidates (category D) in their own waves when possible. D requires per-instance judgment, which slows the agent; mixing them with A/B/C work would slow autonomous-deletion work too.
3. **Write the wave plan** to `.mz/task/<task_name>/cleanup_plan.md` so the verification phase can compare expected vs actual edits.

## 3.2 Dispatch a wave

Send all agents in a wave as **parallel tool calls in a single message**. Per the repo's parallel-fan-out cap (6), do not exceed MAX_PARALLEL_AGENTS per message.

Each cleaner gets this dispatch (compressed — the agent definition carries the full process / status protocol / preservation rules; this prompt only carries task-specific context):

```
Task: Clean leftover artifacts in the listed files per the approved detection.md plan.

Detection input: .mz/task/<task_name>/detection.md
Pattern catalog: plugins/mz-dev-pipe/skills/clean-leftovers/references/artifact-catalog.md (grep per category — do not read whole file)
Web research:    .mz/task/<task_name>/web_research.md (additional patterns from Phase 1)

Files in this work unit:
  - <path 1>
  - <path 2>
  - ...

Category guidance:
  A. AI signatures & watermarks  — delete autonomously. No per-instance review.
  B. Pipeline phase markers      — delete autonomously. No per-instance review.
  C. Planning/generation comments — delete autonomously. No per-instance review.
  D. WHAT-not-WHY candidates     — per-instance decision required. Keep when the comment captures a real WHY (numbers/units, regulatory note, "because"/"due to"/"to avoid" patterns, perf workaround, surprising-behavior callout). Delete when it merely restates the next line.
  E. Dead code & half-implementations — delete commented-out blocks ≥ 3 lines unless adjacent live code references them. Replace NotImplementedError stubs ONLY when the dispatch's per-file plan flags decision: delete-stub. Leave unused imports for the linter in Phase 4.

Preservation rules (do not modify):
  - Code blocks inside string literals, docstrings used as test fixtures, or example sections of doc-comments.
  - File headers with legitimate license / copyright text.
  - Comments containing numbers + units, named references (RFC, CVE, ticket IDs), or "because"/"due to"/"to avoid" — these are WHY content even if structurally similar to flagged WHAT comments.
  - Anything inside fenced code blocks of markdown files (would need explicit markdown override from user).

Output report: .mz/task/<task_name>/cleanup_wave_<N>_agent_<M>.md
Status protocol: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED — exactly one terminal line.
```

Replace `<task_name>`, `<N>` (wave number), `<M>` (agent index in wave) per dispatch.

## 3.3 Per-wave checkpoint

After all agents in the wave return:

1. Read each `cleanup_wave_<N>_agent_<M>.md` report.
2. Aggregate: total files edited, hits removed per category, NEEDS_CONTEXT / BLOCKED reports.
3. Update `state.md`:
   - `Phase: 3` (or `Phase: 3.<wave>` for multi-wave runs).
   - `Iteration` unchanged (iteration counts cleanup→verify cycles, not waves within a single cleanup pass).
   - Append all cleanup-wave report paths to `FilesWritten`.
   - Append per-category removal counts to `cleanup_counters` (cumulative across waves).

If any agent returned `BLOCKED` for a non-recoverable reason (file locked, syntax that would corrupt on edit), escalate via AskUserQuestion before the next wave. Options: `skip` (mark the file as residual and continue), `retry` (re-dispatch with adjusted scope), `abort` (stop cleanup, jump to verification with partial results).

If any agent returned `NEEDS_CONTEXT` (e.g., uncertainty on a borderline D candidate), the orchestrator re-dispatches with the per-instance answer added to the prompt. Do not auto-decide D candidates without user input when the agent itself was uncertain.

## 3.4 Next wave or hand off

- If unprocessed file chunks remain → repeat 3.2 / 3.3 with the next wave.
- If all chunks processed → update `state.md` with `Phase: 4`, read `phases/verification.md`, proceed.

## 3.5 Cleanup loop iterations

Phase 3 may be re-entered from Phase 4 when verification finds residuals. The iteration counter (`Iteration` in `state.md`) advances at the cleanup→verify→cleanup boundary, not within a single cleanup pass.

On re-entry from Phase 4:

1. Read `.mz/task/<task_name>/residuals.md` (written by verification).
2. Build a NEW wave plan targeting only the residual file:line hits.
3. Dispatch with an additional instruction: `This is iteration <Iteration> of cleanup. Previous waves missed the listed residuals. Focus exclusively on these hits — do not re-scan other files.`
4. Cap at MAX_FIX_ITERATIONS total cleanup passes. If residuals remain at the cap, the verification phase escalates instead of looping again.

## 3.6 Safety rails

- **Never touch this skill's own files** (`plugins/mz-dev-pipe/skills/clean-leftovers/**`) regardless of scope — the cleaner would otherwise self-destruct its own pattern catalog.
- **Never touch the naturalize agent or skill** (`plugins/mz-creative/skills/naturalize/**`, `plugins/mz-creative/agents/expert-naturalizer.md`) — they legitimately quote AI patterns.
- **Never touch guideline files** (`guidelines/**`) — they document the patterns being cleaned.
- **Never edit any agent file under `plugins/*/agents/*.md`** — agent prompts use STATUS: tokens as load-bearing protocol; deletion would break orchestration. The orchestrator's scope-resolution in Phase 0 already excludes these, but the cleaner enforces it as a hard rail too.

If a dispatch's file list violates a safety rail, the cleaner returns `BLOCKED` immediately with the rail name. The orchestrator removes the file from scope and re-dispatches the remaining list.
