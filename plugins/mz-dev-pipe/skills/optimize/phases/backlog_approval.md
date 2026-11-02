# Phase 3.5: Backlog / Strategy Approval

**Approval gate**, once per loop iteration. The user approves the *strategy* — which hypotheses to pursue and in what order — before any candidate code is written. This is where a cross-module or architectural strategy gets explicit sign-off.

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/backlog.md` with the Read tool and capture its full contents into context.

**State**: write `state.md` with the artifact path and `what_remains: [awaiting approval: backlog]`; `Status` stays `running`.

**Surface 1 — emit the plan message.** Output the backlog verbatim as a normal markdown chat message. Emit the full verbatim contents of `<PROJECT_ROOT>/.mz/task/<task_name>/backlog.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Hypothesis backlog ready for review — optimize

Profiling found the dominant bottleneck. The backlog below ranks the falsifiable speedup hypotheses by impact × confidence ÷ effort; approving authorizes the candidate loop to pursue them top-down.

<verbatim contents of backlog.md>

---
**Approve** → proceed to Phase 4 (candidate generation & verification)  ·  **Reject** → mark task aborted  ·  reply with feedback to revise

Approve cost (estimated): per hypothesis ≈ 4 candidate agents (Opus) + 4 serial measurements (Haiku) × ~22k tokens ≈ ~$<Y.YY>
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the backlog in the question body, it lives in the plan message above:

- question: `The hypothesis backlog above is ready for review.`
- header: `Backlog`
- options: **Approve** — proceed to Phase 4 (candidate generation & verification) · **Reject** — mark task aborted

**Response handling:**

- **Approve** → add `- backlog approved (iteration <N>): .mz/task/<task_name>/backlog.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, read `phases/candidate_loop.md`, and proceed to Phase 4.
- **Reject** → `Status: aborted_by_user`, stop.
- **Any other reply (feedback)** → re-rank in Phase 3, overwrite `backlog.md`, return to this gate, re-read `backlog.md`, and re-emit the entire plan message from scratch with the full new contents. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 4 without explicit approval.
- **Unattended** (`unattended: true` in `state.md`) → `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode": emit Surface 1, skip Surface 2, continue as on Approve, and log the gate in chat, under `## Auto-approvals`, in the journal and in the final report.
- **No answer** → set `Status: blocked`, keep `awaiting approval: backlog`, stop. A missing answer is never approval.
