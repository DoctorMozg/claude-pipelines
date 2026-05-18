# Phase 5: Validation & Results

**Goal**: Confirm the promoted winner's speedup survives a fresh, clean measurement and that the change is sound — then present a measured before / after for user sign-off before the change is banked.

Phase 5 runs once per loop iteration, after a winner is promoted. It ends in an **approval gate**: the user banks the iteration's change or rejects it.

## 5.1 Re-measure the promoted winner

The Phase 4 winner was measured in its own worktree. Re-measure it now **in the working tree**, with a fresh `pipeline-measure-runner` dispatch — a clean, independent measurement confirms the win was the change itself, not a worktree artifact or a measurement fluke.

```
Run the validation measurement for the promoted optimization winner.

Measurement command:  <measure_command from contract.md>
Repetitions:          <measure_reps>
Warmup repetitions:   <measure_warmup>
Noise ceiling (CV):   <noise_ceiling_cv>
Output artifact:      .mz/task/<task_name>/measurements/iter<N>_validated.md

Run the warmup reps and discard them, then the measured reps. Parse exactly one
scalar per rep. Compute mean, median, and coefficient of variation. Write the
artifact with the summary statistics and every raw per-rep value.

Never fabricate a number. An unparseable run is BENCHMARK UNRELIABLE with the raw
output — do not substitute a guessed value.
```

Apply the gates again to the validation run:

- CV over `noise_ceiling_cv` → `BENCHMARK UNRELIABLE`; the validation did not hold. Revert the promotion, record a `DEAD END` in the history buffer, and return to Phase 4 for the next hypothesis.
- Improvement fell below `SIGNIFICANCE_THRESHOLD` on the clean run → the worktree number did not reproduce. Same handling — revert, record, return to Phase 4.
- Improvement holds at or above the threshold with CV within the ceiling → the win is confirmed; continue.

## 5.2 Review the change

For a `code` or `build_pipeline` target — and the `code`-domain components of a `system` target — dispatch `pipeline-code-reviewer` on the promoted diff:

```
Review a performance-optimization diff for correctness and quality.

Diff:     <the promoted change>
Context:  this change was measured to improve <metric> by <measured>% and passed
          <correctness_command>. Review it for behavioral regressions, edge cases
          the correctness suite may miss, and maintainability.

Report findings by severity. Do not re-optimize — review only.
```

For `container`, `llm_hyperparams`, and `generic` targets there is no source diff to review; rely on the correctness gate (or the Phase 4.7 manual checkpoint) and skip this step.

## 5.3 Confidence rating

Rate confidence in the banked change from **measured signals only** — never from how convincing the change looks:

- **High** — improvement at or above threshold, CV well within the ceiling, correctness green (or the manual checkpoint passed), no high-severity review finding.
- **Medium** — the win holds but with a caveat: CV near the ceiling, a medium-severity review finding, or a `HYPOTHESIS UNVERIFIED` tag on the hypothesis.
- **Low** — the win is marginal, or a review finding or correctness concern is unresolved. A low-confidence change is not banked without explicit user direction.

## 5.4 Validation sign-off gate

**Approval gate.** Present the iteration's result for sign-off. See [`../../shared/approval-gate.md`](../../shared/approval-gate.md) for the two-surface pattern and the `MZ_DEV_PIPE_AUTO_APPROVE` bypass.

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/measurements/iter<N>_validated.md` with the Read tool and capture its full contents into context. Also capture the promoted diff, correctness result, review findings, and confidence rating.

**Surface 1 — emit the plan message.** Output the iteration result verbatim as a normal markdown chat message. Emit the full verbatim contents of the validation measurement artifact and supporting results — do not substitute a path, summary, or placeholder. Structure:

```
## Iteration <N> result ready for review — optimize

<H# title> was applied and measured. <metric>: <baseline> → <validated> <unit>
(<measured>% <faster|smaller|cheaper>, harness-sourced, CV <cv>).
Correctness: <status>. Review: <clean | N findings>. Confidence: <high|medium|low>.

<verbatim contents of iter<N>_validated.md>

<verbatim diff of the promoted change>

<verbatim correctness result and review findings>

---
**Approve** → bank this change; the loop re-profiles (Phase 6)  ·  **Reject** → revert this change; record it and re-enter Phase 4 for the next hypothesis  ·  reply with feedback to revise

Every number above traces to a measurement artifact under .mz/task/<task_name>/measurements/.
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the iteration result in the question body, it lives in the plan message above:

- question: `The iteration result above is ready for sign-off.`
- options: **Approve** — bank this change, the loop re-profiles (Phase 6) · **Reject** — revert this change, record it and re-enter Phase 4 for the next hypothesis

**Response handling:**

- **Approve** → the change is banked. Record the new running-best value and proceed to Phase 6.
- **Reject** → revert the promoted change, record it in the history buffer, and re-enter Phase 4 for the next backlog hypothesis (or Phase 6 if the backlog is exhausted).
- **Any other reply (feedback)** → apply the requested adjustment, re-validate from §5.1, return to this gate, re-read the updated artifacts, and re-emit the entire plan message from scratch with the full new result. This is a loop — repeat until the user explicitly approves. Never bank the change without explicit approval.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** → bypass per `../../shared/approval-gate.md`; log `auto-approved (unattended mode)`. The Phase 4.7 manual checkpoint is **not** covered by this bypass — if the contract is `manual`, that checkpoint already ran in Phase 4 with a real human.

## 5.5 Record and proceed

- Update `state.md`: `Phase: 5`, `PhaseName: validate`, the banked value, `FilesWritten`, and the `## History` entry for the banked win — including the validated measurement-artifact path.
- Mark the Phase 5 task tracker done.

Proceed to Phase 6. Read `phases/terminate.md`.
