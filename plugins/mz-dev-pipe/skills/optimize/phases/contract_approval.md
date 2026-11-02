# Phase 0.5: Contract Approval

**Approval gate.** No measurement runs before the contract is approved. See `<PLUGIN_ROOT>/shared/approval-gate.md` for the two-surface pattern, the `MZ_DEV_PIPE_AUTO_APPROVE` unattended-mode bypass, and the cost-preview format.

**Draft the contract.** Determine `target_type` (from `type:` or inferred from the target), then assemble `<PROJECT_ROOT>/.mz/task/<task_name>/contract.md`:

- `target_type: code` → dispatch `pipeline-tooling-detector` with `project_root: <PROJECT_ROOT>` to auto-fill `measure_command`, `correctness_command`, and `change_space` from project manifests.
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

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/contract.md` with the Read tool and capture its full contents into context.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: contract]`; `Status` stays `running`.

**Surface 1 — emit the plan message.** Output the contract verbatim as a normal markdown chat message. Emit the full verbatim contents of `<PROJECT_ROOT>/.mz/task/<task_name>/contract.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Contract ready for review — optimize

The contract below fully specifies this run: target, metric, the measurement and correctness commands, the allowed change space, and the iteration cap. Every later phase reads it; no measurement runs until you approve it.

<verbatim contents of contract.md>

---
**Approve** → proceed to Phase 1 (Baseline)  ·  **Reject** → mark task aborted, no measurement runs  ·  reply with feedback to revise

Reminder: quiesce the measurement host before approving — background load inflates measurement noise and can hard-block the baseline.
Approve cost (estimated): baseline + profile ≈ 3 agents (test-runner, measure-runner, researcher) × ~18k tokens ≈ ~$<Y.YY> on mixed Sonnet + Haiku
```

Use the `<PLUGIN_ROOT>/shared/approval-gate.md` formula for the dollar estimate.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the contract in the question body, it lives in the plan message above:

- question: `The contract above is ready for review.`
- header: `Contract`
- options: **Approve** — proceed to Phase 1 (Baseline) · **Reject** — mark task aborted, no measurement runs

**Response handling:**

- **Approve** → permitted only if every field is concrete (no `<NEEDS USER INPUT>` remains). Add `- contract approved: .mz/task/<task_name>/contract.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, read `phases/baseline.md`, and proceed to Phase 1.
- **Reject** → set `Status: aborted_by_user` and stop.
- **Any other reply (feedback)** → apply the changes / supplied values, overwrite `contract.md`, return to this gate, re-read `contract.md`, and re-emit the entire plan message from scratch with the full new contents — never diff-only, since context compaction may have destroyed the user's memory of earlier iterations. Then re-present the selector. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 1 without explicit approval.
- **Unattended** (`unattended: true` in `state.md`) → `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode": emit Surface 1, skip Surface 2, continue as on Approve, and log the gate in chat, under `## Auto-approvals`, in the journal and in the final report. An incomplete contract takes the No-answer path instead, with `awaiting answer: fill the <NEEDS USER INPUT> fields` in `what_remains`.
- **No answer** → set `Status: blocked`, keep `awaiting approval: contract`, stop. A missing answer is never approval.
