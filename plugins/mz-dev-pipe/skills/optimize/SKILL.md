---
name: optimize
description: >-
  ALWAYS invoke when the user wants to make something faster / smaller / cheaper —
  "optimize", "make it faster", "profile the hotspot", "reduce the image size",
  "tune LLM hyperparameters", "speed up the build". Iterative, measurement-driven
  performance optimization for code, containers, LLM hyperparameters, and build
  pipelines. NOT for removing dead code / unused imports — that is the cleanup skill.
argument-hint: '[scope:branch|global|working] [type:code|container|llm_hyperparams|build_pipeline|system] <target + metric + goal>'
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Performance Optimization Pipeline

## Overview

Orchestrates iterative, measurement-driven performance optimization of any optimizable system — source code, container images and services, LLM hyperparameters, build pipelines, or a composite of these. Each iteration measures, profiles the dominant bottleneck, forms falsifiable speedup hypotheses, generates candidate changes, and verifies each one by measurement — banking only a change a benchmark proves faster and a correctness check proves safe.

Two principles are structural, not advisory:

- **Measure first, always.** No optimization before a trustworthy baseline exists. Profiling precedes hypothesizing; hypothesizing precedes changing. Every speedup number originates from the measurement harness (`pipeline-measure-runner`) — never from model narration.
- **The model generates candidates; measurement decides.** LLMs reliably pick the wrong bottleneck and over-claim speedups. This pipeline uses the model as a candidate *generator* and a deterministic harness as the *evaluator*. A change that was not measured is not a speedup.

The skill is **domain-generic**. The methodology — the scientific loop — is identical across domains; only the measurement command, the profiling technique, and the change space differ. Those three live in a per-run **Optimization Contract** (`contract.md`); the pipeline itself carries zero domain-specific commands. Swap the contract and the same pipeline optimizes a container image instead of a function.

## When to Use

- User wants to make something faster, smaller, or cheaper against a measurable goal.
- Triggers: "optimize X", "make it faster", "profile the hotspot", "reduce the image size", "tune LLM hyperparameters", "speed up the build".
- The target can be measured by a repeatable command — or the user can supply one.
- Domains: source code, container images / services / configs, LLM hyperparameters, build pipelines, and composite `system` targets spanning several of these.

### When NOT to use

- Removing dead code, unused imports, or reducing cyclomatic complexity — use `cleanup`. Cleanup makes code tidier; it does not measure speed.
- A correctness bug or a failing test — use `debug`.
- Making existing code meet quality criteria or pass tests — use `polish`.
- There is no measurable metric and none can be supplied — the skill hard-gates on a measurable goal and cannot run without one.
- Understanding how code works, with no change intent — use `explain`.

## Input

`$ARGUMENTS` — the optimization target, the metric, and the goal. Examples:

- `optimize make src/parser/tokenizer.py 2x faster, p95 under 120ms`
- `optimize type:container reduce the api image below 200MB`
- `optimize type:llm_hyperparams tune sampling params for lowest eval loss`
- `optimize type:system scope:branch cut orchestrator end-to-end latency below 400ms`

Modifiers:

- `scope:` — `branch` | `global` | `working`; bounds which files / artifacts a candidate change may touch.
- `type:` — `code` | `container` | `llm_hyperparams` | `build_pipeline` | `system` | `generic`; selects the contract auto-detect path. If omitted, it is inferred from the target in Phase 0.5.

If `$ARGUMENTS` is empty, or names no measurable metric, the Phase 0 Goal Declaration gate collects it before the run proceeds.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands.

- **Default** (no `scope:`): all project files / artifacts eligible for candidate changes.
- `scope:` controls **which files / artifacts a candidate may edit**. Profiling and measurement are never scope-bound — the profiler reads whatever it needs and the harness runs the whole `measure_command`. The contract's `scope` field records the resolved value; a candidate change that would cross it triggers the Phase 4.5 boundary pause.

## Constants

| Constant                       | Value       | Bounds                                                          |
| ------------------------------ | ----------- | --------------------------------------------------------------- |
| `MAX_OPTIMIZE_ITERATIONS`      | 6           | Phase 2→6 loop hard cap                                         |
| `CANDIDATE_COUNT`              | 4           | parallel `pipeline-perf-candidate` agents per hypothesis        |
| `SIGNIFICANCE_THRESHOLD`       | 0.10        | minimum measured improvement to keep a candidate                |
| `CV_CEILING`                   | 0.10        | measurement-noise hard-block ceiling (coefficient of variation) |
| `MEASURE_REPS`                 | 10          | default benchmark repetitions                                   |
| `MEASURE_WARMUP`               | 3           | default warmup repetitions (discarded)                          |
| `DIMINISHING_RETURNS_WINDOW`   | 2           | iterations of sub-threshold gain before stopping                |
| `MAX_CANDIDATE_REVIEW_RETRIES` | 2           | retries when a candidate agent returns malformed output         |
| `TASK_DIR`                     | `.mz/task/` | task-state root                                                 |

`MEASURE_REPS`, `MEASURE_WARMUP`, `CV_CEILING`, and `MAX_OPTIMIZE_ITERATIONS` seed the matching `contract.md` fields (`measure_reps`, `measure_warmup`, `noise_ceiling_cv`, `iteration_cap`). Once the contract is approved, the contract's values are authoritative for the run — the contract is the per-run source of truth.

## Core Process

### Phase Overview

| Phase | Goal                                   | Reference                           | Gate                     |
| ----- | -------------------------------------- | ----------------------------------- | ------------------------ |
| 0     | Setup + Goal Declaration               | inline below                        | Hard                     |
| 0.5   | Contract Approval                      | inline below                        | Approval                 |
| 1     | Baseline                               | `phases/baseline.md`                | Hard                     |
| 2     | Profile & Classify Bottleneck          | `phases/profile_and_hypothesize.md` | —                        |
| 3     | Hypothesis Generation & Prioritization | `phases/profile_and_hypothesize.md` | —                        |
| 3.5   | Backlog / Strategy Approval            | inline below                        | Approval                 |
| 4     | Candidate Generation & Verification    | `phases/candidate_loop.md`          | autonomous (risk-tiered) |
| 4.5   | Mid-loop Boundary Pause                | inline below                        | Conditional              |
| 4.7   | Manual Correctness Checkpoint          | inline below                        | Conditional              |
| 5     | Validation & Results                   | `phases/validate_and_results.md`    | Approval                 |
| 6     | Termination Decision                   | `phases/terminate.md`               | loop-back / stop         |

The loop is Phase 2 → 3 → 3.5 → 4 → (4.5 / 4.7 as triggered) → 5 → 6; Phase 6 either loops back to Phase 2 (re-profile — the bottleneck has moved) or stops. Phases 0, 0.5, and 1 run exactly once. Read each phase file when you reach it — do not load all phase files upfront.

### Phase 0: Setup + Goal Declaration

**Hard gate** — the pipeline cannot proceed without a measurable goal.

1. **Parse input** — extract `scope:`, `type:`, and the free-text target + metric + goal from `$ARGUMENTS`.
1. **Resolve scope** — per [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md); save the resolved file list to `.mz/task/<task_name>/scope_files.txt`. No `scope:` → all project files / artifacts eligible.
1. **Task name** — `<YYYY_MM_DD>_optimize_<slug>`, where `<slug>` is a snake_case summary of the target (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. **Resume check** — apply the resume contract in [`skills/shared/resume-protocol.md`](../shared/resume-protocol.md): if `.mz/task/<task_name>/state.md` exists with `Status: running | failed`, present the Resume gate. A pre-existing `state.md` **without** a `skill_variant: methodology` key belongs to the renamed `cleanup` skill's task history, not this skill — do not resume into it; pick a fresh `_vN` name.
1. **Task dir & state** — create `.mz/task/<task_name>/`; write `state.md` per [`skills/shared/state-schema.md`](../shared/state-schema.md): `schema_version: 1`, then `Status`, `Phase`, `PhaseName`, `Started`, `Iteration` (0), `FilesWritten`, plus skill-specific keys `skill_variant: methodology`, `Target`, `Metric`, `Goal`, `TargetType`, and an empty `## History` section (the persistent record of every hypothesis tried and its measured outcome — it survives context compaction and stops a failed transform from being retried).
1. **Task tracking** — TaskCreate per pipeline phase.

**Goal Declaration.** The pipeline cannot proceed without a *measurable* goal. A measurable goal has three parts: a **metric** (what is measured), a **unit**, and either a **target value** or an explicit **"best effort"** (optimize as far as the iteration cap allows).

- If any part is missing — e.g. "make it faster" with no metric and no unit — emit `BUDGET MISSING` and ask the user, via AskUserQuestion, for the missing parts. Never guess a metric or a target. Do not proceed.
- Once all three parts are present → emit `BUDGET DECLARED`, record `Metric` and `Goal` in `state.md`, and proceed to Phase 0.5.

The "budget" is the performance budget — the measurable goal the whole loop is held to.

### Phase 0.5: Contract Approval

**Approval gate.** No measurement runs before the contract is approved. See [`skills/shared/approval-gate.md`](../shared/approval-gate.md) for the two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format.

**Draft the contract.** Determine `target_type` (from `type:` or inferred from the target), then assemble `.mz/task/<task_name>/contract.md`:

- `target_type: code` → dispatch `pipeline-tooling-detector` to auto-fill `measure_command`, `correctness_command`, and `change_space` from project manifests.
- `target_type: container | llm_hyperparams | build_pipeline | system | generic` → propose defaults from domain knowledge. For any domain outside confident coverage, dispatch `pipeline-researcher` (with `WebFetch` / `WebSearch`) for current best practice before drafting. Mark any field you genuinely cannot propose `<NEEDS USER INPUT: ...>`.
- `target_type: system` → keep one end-to-end metric and make `change_space` a list of objects, each tagging `{class, domain, paths}`, so the run can attribute the metric across components and follow the bottleneck as it moves between domains.

Contract template:

```yaml
target_system:       "<what is optimized — file::function, image name, service, …>"
target_type:         code        # code | container | llm_hyperparams | build_pipeline | system | generic
metric_name:         <e.g. p95_latency>
metric_unit:         <e.g. ms>
metric_direction:    minimize    # minimize | maximize
target_value:        <number, or null for best-effort within the iteration cap>
baseline_value:      null        # filled by Phase 1
measure_command:     "<command emitting one parseable scalar — a JSON field or a trailing numeric line>"
measure_reps:        10
measure_warmup:      3
noise_ceiling_cv:    0.10        # hard-block if the measured CV exceeds this
correctness_command: "<test command>"   # or the literal: manual
change_space:        [<allowed transformation classes>]   # objects {class, domain, paths} for target_type: system
scope:               working     # working | branch | global
iteration_cap:       6
```

**Present the gate.** Emit the chat-visible pre-gate block:

```
**Optimization Contract — Review**
The contract below fully specifies this run: target, metric, the measurement and correctness commands, the allowed change space, and the iteration cap. Every later phase reads it; no measurement runs until you approve it.

- **Approve** → proceed to Phase 1 (Baseline)
- **Reject** → mark task aborted, no measurement runs
- **Feedback** → supply any `<NEEDS USER INPUT>` field or change any value; the contract is re-drafted and re-presented

Reminder: quiesce the measurement host before approving — background load inflates measurement noise and can hard-block the baseline.
Approve cost (estimated): baseline + profile ≈ 3 agents (test-runner, measure-runner, researcher) × ~18k tokens ≈ ~$<Y.YY> on mixed Sonnet + Haiku
```

Use the `shared/approval-gate.md` formula for the dollar estimate. Then invoke AskUserQuestion with the **verbatim** `contract.md` contents in the body, closing with `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

**Response handling:**

- **Approve** → permitted only if every field is concrete (no `<NEEDS USER INPUT>` remains). Update state, read `phases/baseline.md`, proceed to Phase 1.
- **Reject** → set `Status: aborted_by_user` and stop.
- **Feedback** → apply the changes / supplied values, overwrite `contract.md`, re-read it, and re-present this gate via AskUserQuestion with the full new contents — never diff-only, since context compaction may have destroyed the user's memory of earlier iterations. Loop until approved.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** → per `shared/approval-gate.md`: skip the AskUserQuestion call, log `auto-approved (unattended mode)`, and proceed — but only if no `<NEEDS USER INPUT>` field remains; an incomplete contract can never be auto-approved.

### Phase 3.5: Backlog / Strategy Approval

**Approval gate**, once per loop iteration. The user approves the *strategy* — which hypotheses to pursue and in what order — before any candidate code is written. This is where a cross-module or architectural strategy gets explicit sign-off.

Pre-read `.mz/task/<task_name>/backlog.md` (the ranked hypothesis backlog from Phase 3). Emit the pre-gate block:

```
**Hypothesis Backlog — Strategy Review**
Profiling found the dominant bottleneck. The backlog below ranks the falsifiable speedup hypotheses by impact × confidence ÷ effort; approving authorizes the candidate loop to pursue them top-down.

- **Approve** → proceed to Phase 4 (candidate generation & verification)
- **Reject** → mark task aborted
- **Feedback** → re-rank, drop, or add hypotheses; the backlog is re-presented

Approve cost (estimated): per hypothesis ≈ 4 candidate agents (Opus) + 4 serial measurements (Haiku) + 1 promotion (Sonnet) × ~22k tokens ≈ ~$<Y.YY>
```

Invoke AskUserQuestion with the **verbatim** `backlog.md` contents, closing with `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

**Response handling:** Approve → read `phases/candidate_loop.md`, proceed to Phase 4. Reject → `Status: aborted_by_user`, stop. Feedback → re-rank in Phase 3, overwrite `backlog.md`, re-present with the full new contents. `MZ_DEV_PIPE_AUTO_APPROVE=1` → bypass per `shared/approval-gate.md`.

### Phase 4.5: Mid-loop Boundary Pause

**Conditional approval gate** — fires *from within* Phase 4, only when a candidate needs a change outside its risk tier. Any one of:

- a **cross-module or architectural** change (beyond a single artifact or module),
- a change to a file / artifact **outside the contract's `scope`**,
- a change of a **transformation class not in `change_space`**.

Low-risk, in-scope, single-artifact changes inside `change_space` do **not** trigger this — they proceed autonomously (the risk-tiered approval model).

When triggered, pause the candidate loop and present, via the two-surface pattern, the specific boundary-crossing change: what it touches, which boundary it crosses, and why the candidate needs it. The user approves *that change* specifically.

**Response handling:** Approve → the candidate proceeds with the boundary-crossing change. Reject → that candidate is discarded as a `DEAD END`; the loop continues with the rest. Feedback → revise and re-present. `MZ_DEV_PIPE_AUTO_APPROVE=1` → bypass per `shared/approval-gate.md`.

### Phase 4.7: Manual Correctness Checkpoint

**Conditional checkpoint** — fires only when the contract's `correctness_command` is the literal `manual`.

With no automated suite, a winning candidate cannot be proven behavior-safe by a command. After such a candidate is promoted into the working tree, pause and ask the user — via AskUserQuestion — to manually confirm the change did not alter observable behavior, comparing against the manual baseline-behavior reference recorded in Phase 1.

This is lighter than an approval gate — a focused yes / no on correctness, not a strategy review:

- **Behavior unchanged** → the candidate is banked; continue to Phase 5.
- **Behavior changed** → the candidate is reverted and recorded as a `DEAD END` in the history buffer; the loop continues.

This checkpoint is **exempt from `MZ_DEV_PIPE_AUTO_APPROVE`** — a human must actually observe the behavior. Auto-approve never satisfies it; running unattended, the loop pauses here and waits.

## Techniques

Techniques: delegated to phase files — see the Phase Overview table.

Reference file: [`references/optimization-toolkit.md`](references/optimization-toolkit.md) — the domain-agnostic bottleneck taxonomy, transformation catalog, profiling principles, prioritization rules, and anti-patterns. Phases 2 and 3 grep it per section; do not load the whole file.

## Common Rationalizations

| Rationalization                                        | Rebuttal                                                                                       |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| "the speedup is obvious, skip the measurement"         | unmeasured is not a speedup — the harness reports the number, never the model                  |
| "CV is a little over the ceiling, close enough"        | a benchmark above the noise ceiling is a coin flip; hard-block and quiesce the host            |
| "the model said it's O(n) now, so it's faster"         | Big-O claims are UNVERIFIED until the harness measures wall-clock — algebra is not a benchmark |
| "optimize the hottest function first"                  | the hottest function is often not the highest-impact target — rank by Amdahl-bounded impact    |
| "all candidates missed the threshold, keep the best"   | a sub-threshold result is a `DEAD END`; banking it banks measurement noise as a "win"          |
| "skip the correctness check, it's just a speed change" | a faster wrong answer is still wrong — most unverified optimizations regress behavior          |

## Red Flags

- A speedup number reached the user that did not originate from a `pipeline-measure-runner` artifact.
- A candidate was banked without a green correctness gate (or, for `manual` contracts, without the Phase 4.7 checkpoint).
- A hypothesis was formed from intuition instead of a measured profile — Phase 2 was skipped or rushed.
- The run continued past a `BENCHMARK UNRELIABLE` baseline.
- A cross-module, out-of-scope, or out-of-`change_space` change was applied without the Phase 4.5 pause.
- The Phase 4.7 manual checkpoint was auto-approved or skipped.
- A "win" below `SIGNIFICANCE_THRESHOLD` was banked anyway.

## Verification

Output the final results block: the contract's metric and goal, the **measured** baseline and final values (each tagged harness-sourced, with its measurement-artifact path), the per-iteration measured gains, the cumulative speedup (geometric mean across iterations), the correctness status of every banked change, the iteration count, and the termination reason. Every number must trace to a `pipeline-measure-runner` artifact under `.mz/task/<task_name>/measurements/`. A results block carrying a number with no artifact path is invalid — do not emit it.

## Error Handling

- **No measurable goal** — Phase 0 emits `BUDGET MISSING`, asks, does not proceed.
- **`measure_command` emits no parseable scalar** — Phase 1 hard-blocks; ask the user to fix the command; never substitute a guessed number.
- **Noisy baseline** (`CV > noise_ceiling_cv`) — Phase 1 emits `BENCHMARK UNRELIABLE` and hard-blocks; the user quiesces the host or raises the ceiling (which returns through the Phase 0.5 gate).
- **Baseline already meets the target** — Phase 1 emits `ALREADY WITHIN BUDGET` and stops successfully.
- **A hypothesis yields no surviving candidate** — emit `DEAD END`, move to the next backlog item, diversify the transformation class.
- **A candidate agent returns malformed output** — retry up to `MAX_CANDIDATE_REVIEW_RETRIES`, then drop that candidate.
- **`pipeline-tooling-detector` cannot detect a command** — fall back to asking the user to supply each contract field.
- **An unfamiliar target domain** — Phase 2 dispatches `pipeline-researcher` with web research; the live profile remains the primary signal.
- Always save state before spawning agents.

## State Management

After each phase and each loop iteration, update `.mz/task/<task_name>/state.md`: the current `Phase` / `PhaseName`, `Iteration`, the current best measured value, `FilesWritten`, and the `## History` buffer. The history buffer records every hypothesis tried, its assigned transformation class, and its measured outcome (banked win / `DEAD END` / `HYPOTHESIS UNVERIFIED`) — Phase 4 reads it so no failed transform is retried, and it is the only reliable cross-iteration memory after context compaction. The `skill_variant: methodology` key is set in Phase 0 and never mutates.
