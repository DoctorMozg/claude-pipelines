# Phase 6: Termination Decision

**Goal**: Decide whether the optimization loop has more useful work to do — loop back to Phase 2 and re-profile, or stop with a final measured-results report.

Phase 6 runs once at the end of every loop iteration. It changes nothing: it reads the run's measured history and routes.

## 6.1 Read the iteration outcome

Read `state.md` — the `## History` buffer and the current running-best measured value. The iteration that just finished reached Phase 6 one of two ways:

- **From Phase 5** — a change was banked; the running-best value moved.
- **From Phase 4** — every hypothesis in the backlog dead-ended; the iteration is recorded as no-gain and the running-best value is unchanged.

Compute this iteration's **per-iteration gain** in the `metric_direction` sense — the improvement of the running-best value over its value at the start of the iteration. A no-gain iteration's per-iteration gain is zero.

## 6.2 Apply the termination conditions

Check these in order. The first that holds stops the loop.

1. **Target met.** `target_value` is set and the running-best value satisfies it (≤ target for `minimize`, ≥ target for `maximize`). → **Stop — success.** Go to §6.4.
1. **Iteration cap reached.** `Iteration` has reached the contract's `iteration_cap`. → **Stop — cap.** Go to §6.4.
1. **Diminishing returns.** The run has completed at least `DIMINISHING_RETURNS_WINDOW` iterations, and each of the last `DIMINISHING_RETURNS_WINDOW` of them (this one included) produced a per-iteration gain below `SIGNIFICANCE_THRESHOLD` — a no-gain / `DEAD END` iteration counts as a sub-threshold iteration. → emit `DIMINISHING RETURNS — stopping` and **stop.** Go to §6.4. With fewer than `DIMINISHING_RETURNS_WINDOW` iterations so far, this condition cannot fire — skip it.
1. **Otherwise.** The target is unmet (or best-effort), the cap is not reached, and the loop is still producing gains. → **Continue.** Go to §6.3.

Why the diminishing-returns stop exists: the loop re-profiles every iteration, so it naturally chases the next bottleneck — but each new bottleneck tends to own a smaller share of the metric than the last. Once two iterations running cannot clear the significance threshold, the bottlenecks that remain are noise-sized; continuing spends the iteration budget for nothing.

## 6.3 Continue — loop back to Phase 2

- Increment `Iteration` in `state.md`; set `Phase: 2`, `PhaseName: profile`.
- The next iteration re-profiles from scratch. The banked change moved the bottleneck, so the previous `profile.md` and `backlog.md` are stale — Phase 2 and Phase 3 regenerate both. Never carry a hypothesis forward from the previous backlog: the bottleneck has moved, and for a `system` target it may have moved to a different component and a different domain.
- The `## History` buffer is **not** reset — it is the cross-iteration memory that stops a failed transformation from being retried.

Proceed to Phase 2. Read `phases/profile_and_hypothesize.md`.

## 6.4 Stop — final report

Set `state.md` `Status: complete`, `Phase: 6`, `PhaseName: terminate`; mark the Phase 6 task tracker done.

Emit the final results block. Every number in it must trace to a `pipeline-measure-runner` measurement artifact under `.mz/task/<task_name>/measurements/`; cite the artifact path beside each. A number with no artifact path is invalid — do not emit it.

```
**Optimization Complete — <task_name>**
Termination reason: <target met | iteration cap reached | DIMINISHING RETURNS — stopping>
Metric:  <metric_name> (<metric_unit>), direction <metric_direction>

Baseline: <baseline_value>            [measurements/baseline.md]
Final:    <running-best value>        [measurements/iter<N>_validated.md]
Target:   <target_value | best effort>   — <met | not met>
Cumulative gain: <X>% <faster|smaller|cheaper>   (geometric mean across banked iterations)

Banked changes (<count>):
- iter<N> — <H# title>: <before> → <after> <unit>   (<gain>%, CV <cv>)   [measurements/iter<N>_validated.md]
- ...

Iterations run: <N> of <iteration_cap>
Correctness:    every banked change passed <correctness_command | the manual checkpoint>.
```

- **Cumulative gain** is the geometric mean of the per-iteration speedup ratios — never the arithmetic sum of the per-iteration percentages. With no banked change the cumulative gain is 0% and the report states that plainly.
- A run that stopped at the cap or on diminishing returns with the target unmet reports a **partial** result honestly — a partial gain is never presented as success.
- Listing each measurement-artifact path lets the user re-check every number independently.

The optimization run is complete.
