# Phase 1: Baseline

**Goal**: Establish a trustworthy, reproducible baseline — the number every later speedup is measured against. This phase profiles nothing and changes nothing; it only confirms the ground is solid before optimization begins.

Phase 1 is a **hard gate**. Three conditions each stop the run here: a red correctness suite, a `measure_command` that emits no parseable number, or a benchmark noisier than the contract's `noise_ceiling_cv`. The pipeline never optimizes against a baseline it cannot trust.

**No code or artifact changes happen in this phase.**

## 1.1 Establish correctness ground truth

Read `.mz/task/<task_name>/contract.md` and branch on `correctness_command`.

**Automated** (`correctness_command` is a command) — dispatch `pipeline-test-runner`:

```
Run the correctness suite for this optimization task's baseline.

Command: <correctness_command from contract.md>

Run it and report pass / fail per test plus the overall result. This establishes the
correctness ground truth — the baseline must be green before any optimization begins.
Do not modify any code.
```

The suite MUST be green. A red baseline is a hard block: with pre-existing failures you cannot tell a regression introduced by a candidate from a failure that was already there. Stop, report which tests fail, and tell the user to fix the suite first (`/debug` for a known failure, `/polish` for general criteria), then re-run `/optimize`. Do not proceed.

`pipeline-test-runner` checks correctness only — pass / fail. It is never the measurement harness; speedup numbers come solely from `pipeline-measure-runner` in step 1.3.

**Manual** (`correctness_command: manual`) — there is no automated suite. Record a manual baseline-behavior reference: capture the observable behavior the optimization must preserve (exact outputs, healthcheck result, response shape, side effects). Present it to the user via AskUserQuestion to confirm it is correct and complete, then write it to `state.md` under `## Manual baseline behavior`. The Phase 4.7 checkpoint compares every winning candidate against this reference.

## 1.2 Validate the measurement command

Run `measure_command` exactly once and confirm its output carries a machine-parseable scalar — the JSON field the contract names, or a trailing numeric line.

If the command errors, emits nothing parseable, or emits a non-numeric value, this is a hard block. Do NOT guess a number and do NOT proceed. Report the command and its actual output, and ask the user to correct `measure_command` so it emits a parseable scalar; a corrected contract returns through the Phase 0.5 approval gate.

This single run only proves the command is well-formed — it is **not** the baseline. Discard its value; warmup effects make one run unreliable.

## 1.3 Measure the baseline

Dispatch `pipeline-measure-runner` — the only source of measurement numbers in this pipeline:

```
Run the baseline measurement for this optimization task.

Measurement command:  <measure_command from contract.md>
Repetitions:          <measure_reps>
Warmup repetitions:   <measure_warmup>
Noise ceiling (CV):   <noise_ceiling_cv>
Output artifact:      .mz/task/<task_name>/measurements/baseline.md

Run the warmup repetitions and discard them, then run the measured repetitions. Parse
exactly one scalar per repetition (the JSON field the command emits, or its trailing
numeric line). Compute mean, median, and coefficient of variation. Write the artifact
with the summary statistics and every raw per-rep value.

Never fabricate a number. If a repetition errors or emits nothing parseable, report it
as BENCHMARK UNRELIABLE with the raw output — do not substitute a guessed value. State
the measured CV explicitly and whether it exceeds the noise ceiling.
```

The orchestrator never computes or narrates a baseline number itself — read it from the artifact.

## 1.4 Hard checks

Read `.mz/task/<task_name>/measurements/baseline.md` and apply, in order:

1. **Noise check.** If the measured CV exceeds `noise_ceiling_cv` → emit `BENCHMARK UNRELIABLE` and hard-block. A benchmark noisier than the ceiling cannot separate a real speedup from host jitter — every later before / after comparison would be a coin flip. Stop and tell the user to quiesce the measurement host (close background load, pin CPU frequency, disable turbo and power-saving) and re-run, or — only if the noise is genuinely irreducible for this metric — raise `noise_ceiling_cv` in the contract, which returns through the Phase 0.5 gate.
1. **Already-met check.** If the baseline already satisfies `target_value` in the `metric_direction` sense (≤ target for `minimize`, ≥ target for `maximize`) → emit `ALREADY WITHIN BUDGET` and stop **successfully**. There is nothing to optimize. Report the baseline value against the target and suggest the user either tighten the target or close the task.
1. Otherwise → the baseline is trustworthy and there is real work to do. Continue.

## 1.5 Record and proceed

- Write the measured baseline into `contract.md` `baseline_value` (the field Phase 0.5 left `null`).
- Update `state.md`: `Phase: 1`, `PhaseName: baseline`, the baseline value and CV, the correctness status, and append an iteration-0 entry to the `## History` buffer recording the baseline.
- Mark the Phase 1 task tracker done.

Proceed to Phase 2. Read `phases/profile_and_hypothesize.md`.
