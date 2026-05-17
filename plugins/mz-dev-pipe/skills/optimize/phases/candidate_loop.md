# Phase 4: Candidate Generation & Verification

**Goal**: Take the top hypothesis from the approved backlog and let measurement — not the model — decide whether it yields a real, behavior-safe speedup worth banking.

Phase 4 is the only phase that changes the target. It is **autonomous within the risk tier**: a low-risk, in-scope, single-artifact change inside `change_space` proceeds with no gate. A change that crosses a boundary triggers the Phase 4.5 pause in `SKILL.md`.

Phase 4 processes **one hypothesis per round**. §4.1-§4.10 are a single round; §4.11 either starts the next round, advances to Phase 5, or advances to Phase 6.

Each round runs in two deliberately split stages:

- **Stage A — implement in parallel.** Up to `CANDIDATE_COUNT` candidates are built concurrently, each in its own worktree. Parallel *implementation* is safe — isolated worktrees never collide.
- **Stage B — measure serially.** Benchmarks run one at a time. Parallel *measurement* is not safe: two benchmarks contending for CPU, cache, and I/O corrupt each other's numbers. This is the deliberate serial-measurement tradeoff — slower wall-clock, trustworthy numbers.

## 4.1 Select the hypothesis

Take the top unattempted hypothesis from `backlog.md`. **First read the `## History` buffer in `state.md`** — every transformation already tried and its outcome. Do not re-dispatch a transformation class already recorded as a `DEAD END` for this bottleneck. If the backlog is exhausted, skip to §4.11.

## 4.2 Stage A — parallel candidate implementation

Dispatch `CANDIDATE_COUNT` `pipeline-perf-candidate` agents in **one** message (parallel), each in its own worktree (`isolation: worktree`).

**Diversification rule.** The candidates must not be four variants of one change. Assign each a *distinct* transformation class — or a distinct mechanism within the hypothesis — drawn from the toolkit's Transformation catalog. Diversity is what makes the round informative: if all four converge on the same edit, the round taught nothing. On a re-entry after a `DEAD END`, the next round diversifies *away* from the failed class entirely.

Dispatch prompt per candidate:

```
Implement ONE performance-optimization candidate. Do not measure it.

Hypothesis:        <H# title and prediction from backlog.md>
Transformation:    <the distinct class assigned to THIS candidate>
Contract:          .mz/task/<task_name>/contract.md
History buffer:    <the ## History block from state.md — transforms already tried>
Allowed scope:     <change_space classes + scope paths from the contract>

Implement exactly one change of the assigned transformation class in your worktree.
Then run the correctness command and report its result:

  correctness_command: <correctness_command from contract.md>

Then STOP. Do NOT benchmark or measure — measurement is serial and orchestrator-driven.

Report: the diff, the correctness result (pass / fail per test + overall), the
transformation class, and which mechanism from the hypothesis you targeted.

If your candidate would require a change OUTSIDE the allowed scope — a cross-module
or architectural change, a file outside the scope paths, or a transformation class
not in change_space — do NOT apply it. Stop, return STATUS: NEEDS_CONTEXT, and put
the specifics under a "Boundary approval needed" section: what it touches, which
boundary it crosses, and why the candidate needs it.
```

**Stack-booting correctness — `target_type: system`.** When `correctness_command` boots a multi-service stack, parallel Stage-A correctness runs collide on host ports and shared resources. The candidate dispatch must then instruct each agent to namespace its stack instance with a per-candidate identifier and bind services to dynamically-allocated host ports. If the stack cannot be namespaced, candidates still implement in parallel but the orchestrator runs the stack-booting correctness step serially, one worktree at a time. Pure file-edit and unit-test correctness always runs in parallel inside the agent.

## 4.3 Stage A gate — candidate returns

Each `pipeline-perf-candidate` agent returns one terminal `STATUS`. Route on it:

- `STATUS: DONE` — the candidate is implemented and `correctness_command` ran green (or, for a `manual` contract, correctness is deferred to the Phase 4.7 checkpoint). The worktree advances to Stage B.
- `STATUS: DONE_WITH_CONCERNS` — the candidate is implemented but `correctness_command` failed. Discard it immediately — a faster wrong answer is not a candidate — and record the correctness failure in the history buffer.
- `STATUS: NEEDS_CONTEXT` with a `## Boundary approval needed` section — the candidate needs a change outside the allowed scope. It does not advance yet; it parks the Phase 4.5 boundary pause (§4.6).
- `STATUS: NEEDS_CONTEXT` for a missing dispatch field — re-dispatch the agent with the field supplied, up to `MAX_CANDIDATE_REVIEW_RETRIES` times, then drop the candidate.
- `STATUS: BLOCKED` — a fundamental obstacle the agent cannot get past. Drop the candidate and record it in the history buffer; do not re-dispatch.
- Malformed output (no parseable terminal `STATUS`) — re-dispatch up to `MAX_CANDIDATE_REVIEW_RETRIES` times, then drop.

Only worktrees that returned `STATUS: DONE` advance to Stage B.

## 4.4 Stage B — serial measurement

For each surviving worktree, dispatch `pipeline-measure-runner` — **one per orchestrator turn**, never two in the same message. Wait for each to finish before dispatching the next.

```
Run the candidate measurement for one optimization candidate.

Measurement command:  <measure_command from contract.md>
Run inside worktree:  <candidate worktree path>
Repetitions:          <measure_reps>
Warmup repetitions:   <measure_warmup>
Noise ceiling (CV):   <noise_ceiling_cv>
Output artifact:      .mz/task/<task_name>/measurements/iter<N>_candidate<M>.md

Run the warmup reps and discard them, then the measured reps. Parse exactly one
scalar per rep. Compute mean, median, and coefficient of variation. Write the
artifact with the summary statistics and every raw per-rep value.

Never fabricate a number. If a rep errors or emits nothing parseable, report it as
BENCHMARK UNRELIABLE with the raw output — do not substitute a guessed value. State
the measured CV and whether it exceeds the ceiling.
```

## 4.5 Gate each candidate

For each measured candidate, read its measurement artifact and apply, in order:

1. **Noise gate.** Measured `CV > noise_ceiling_cv` → discard; the number is untrustworthy. The artifact is already tagged `BENCHMARK UNRELIABLE`.
1. **Significance gate.** Measured improvement (in the `metric_direction` sense) below `SIGNIFICANCE_THRESHOLD` → discard. A sub-threshold delta is indistinguishable from noise; banking it banks noise as a "win".
1. **Survivor.** Correctness-green, CV within the ceiling, improvement at or above the threshold → a valid survivor.

Append **every** candidate — survivor and discard alike — to the `## History` buffer in `state.md`: hypothesis, transformation class, measured value, CV, and outcome. The history buffer is what stops a future iteration from re-trying a failed transform.

## 4.6 Boundary pause — when a candidate needs it

If any candidate returned `STATUS: NEEDS_CONTEXT` with a `## Boundary approval needed` section, run the **Phase 4.5 Mid-loop Boundary Pause** in `SKILL.md` for that change. On approval, re-dispatch that candidate agent with the boundary change authorized, then measure it (§4.4) and gate it (§4.5). On rejection, the candidate is discarded as a `DEAD END` and the round continues with the rest.

## 4.7 HYPOTHESIS UNVERIFIED check

For each survivor, compare the measured outcome against the hypothesis's *prediction*. If the result contradicts the predicted mechanism — a change predicted to help that did not, or a win whose magnitude or cause does not match the predicted mechanism — tag the hypothesis `HYPOTHESIS UNVERIFIED` in the history buffer. The candidate may still win on measured merit; the *hypothesis* is marked unverified so the next iteration does not over-trust the same reasoning.

## 4.8 Winner promotion

Among survivors, the winner is the candidate with the best measured value (on a tie, lowest CV, then lowest risk). Promote its diff into the working tree by dispatching `pipeline-coder`:

```
Promote a verified optimization candidate into the working tree.

Source diff:  <the winning candidate's diff, or its worktree path>
Apply to:     the main working tree

Apply the diff exactly — do not re-optimize, re-design, or "improve" it. It is
already measured; any edit invalidates the measurement. After applying, confirm the
file(s) apply cleanly with no conflict.
```

If the contract's `correctness_command` is `manual`, run the **Phase 4.7 Manual Correctness Checkpoint** in `SKILL.md` now, before continuing — a human must confirm behavior is unchanged before the candidate is banked.

## 4.9 No survivors — DEAD END

If no candidate survived §4.5 for this hypothesis, emit `DEAD END` for it and record it in the history buffer. The round produced no win; §4.11 decides what happens next.

## 4.10 Worktree cleanup

Before §4.11, **remove every candidate worktree** from this round — the winner's diff is already promoted into the working tree by `pipeline-coder`; the losers are discarded. Leave no orphan worktree. Verify the cleanup with the orchestrator's git tooling. This runs every round, win or `DEAD END`.

## 4.11 Round outcome & routing

- Update `state.md`: `Phase: 4`, `PhaseName: candidate_loop`, the current best measured value, the round's outcome, and the appended `## History` entries.
- Mark the Phase 4 task tracker done.

Then route:

- **A winner was promoted** → proceed to Phase 5. Read `phases/validate_and_results.md`.
- **`DEAD END`, backlog still has hypotheses** → return to §4.1 for the next hypothesis, diversifying the transformation class away from the dead end.
- **`DEAD END`, backlog exhausted** → no hypothesis for this bottleneck produced a win. Proceed to Phase 6 with this iteration recorded as no-gain. Read `phases/terminate.md`.
