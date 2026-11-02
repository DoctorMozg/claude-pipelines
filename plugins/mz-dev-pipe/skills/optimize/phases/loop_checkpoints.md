# Phases 4.5 and 4.7: Loop Checkpoints

## Phase 4.5: Mid-loop Boundary Pause

**Conditional approval gate** — fires *from within* Phase 4, only when a candidate needs a change outside its risk tier. Any one of:

- a **cross-module or architectural** change (beyond a single artifact or module),
- a change to a file / artifact **outside the contract's `scope`**,
- a change of a **transformation class not in `change_space`**.

Low-risk, in-scope, single-artifact changes inside `change_space` do **not** trigger this — they proceed autonomously (the risk-tiered approval model).

When triggered, pause the candidate loop and present, via the two-surface pattern, the specific boundary-crossing change: what it touches, which boundary it crosses, and why the candidate needs it. The user approves *that change* specifically.

**Response handling:** Approve → the candidate proceeds with the boundary-crossing change. Reject → that candidate is discarded as a `DEAD END`; the loop continues with the rest. Feedback → revise and re-present. `MZ_DEV_PIPE_AUTO_APPROVE=1` → bypass per `<PLUGIN_ROOT>/shared/approval-gate.md`.

## Phase 4.7: Manual Correctness Checkpoint

**Conditional checkpoint** — fires only when the contract's `correctness_command` is the literal `manual`.

With no automated suite, a winning candidate cannot be proven behavior-safe by a command. After such a candidate is promoted into the working tree, pause and ask the user — via AskUserQuestion — to manually confirm the change did not alter observable behavior, comparing against the manual baseline-behavior reference recorded in Phase 1.

This is lighter than an approval gate — a focused yes / no on correctness, not a strategy review:

- **Behavior unchanged** → the candidate is banked; continue to Phase 5.
- **Behavior changed** → the candidate is reverted and recorded as a `DEAD END` in the history buffer; the loop continues.

This checkpoint is **exempt from `MZ_DEV_PIPE_AUTO_APPROVE`** — a human must actually observe the behavior. Auto-approve never satisfies it. Nobody will come when the run is unattended, so it takes the No-answer path (`<PLUGIN_ROOT>/shared/approval-gate.md`): set `Status: blocked`, record `awaiting answer: manual correctness check` in `what_remains`, and stop.
