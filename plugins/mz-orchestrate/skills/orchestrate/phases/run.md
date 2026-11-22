# Phase 2: Run the DAG

Expand `<PROJECT_ROOT>`, `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<TASK_DIR>` before every Read, command and dispatch prompt. `DAG` is `<TASK_DIR>/dag.json`; `dag.sh` and `integrate.sh` are the scripts under `<PLUGIN_ROOT>/scripts/`. Every unit status change goes through `dag.sh mark`, and state.md records only the phase, the integration worktrees and any gate that is waiting.

You orchestrate only. Workers write the code; the resolver resolves conflicts; you dispatch, merge, verify and ask.

Read `<SKILL_DIR>/phases/backends.md` before the first dispatch: it says how each backend is dispatched, how its result comes back, and how silent units are caught.

## Step 0: Reconcile after a restart

Run this step only when resuming a task whose `Phase` is `run`. The old session's subagents and headless sessions died with it; peers, `--bg` sessions and git kept the truth.

1. For each repository under `integration`: when `git -C <worktree> rev-parse -q --verify MERGE_HEAD` succeeds, a merge was cut short: `integrate.sh abort <worktree>`. Then run Step 1's `init` again, which reuses the worktree.
1. When REGISTRY lists attached peers, re-attach them, because their attachment names the old session's address: invoke `mz-orchestrate:orchestrate-attach` with each peer's name and its stored `role.note`.
1. For each unit `dag.sh DAG list done` prints with `kind: change`: merge it (Step 4).
1. For each unit `dag.sh DAG list running`:
   - On a peer: send `ORCH-STATUS` and handle the answer as backends.md says.
   - On a `--bg` session (`backend_used: session:bg`): its `reply-to` names the old session, so its result can't arrive. Run `session.sh stop` with the session id from its `note`, then treat it as the cases below do.
   - Otherwise, when its `branch` exists with a commit beyond `base_commit` (`git -C <repo> rev-list --count <base_commit>..<branch>`), the worker finished its commit before the restart: `dag.sh DAG mark <id> done head_commit=<branch tip> note=resumed` and treat it as `DONE` in Step 3, which checks scope and merges with verify. It is not run again.
   - Otherwise nothing of it survived: clean up its worktree as in Step 4, using the unit's recorded `worktree` and `worktree_branch`, or, for a subagent that never reported, the entry of `git -C <repo> worktree list --porcelain` on `branch`. Then `dag.sh DAG requeue <id>`, which doesn't count the lost attempt, and Step 2 runs it again.
1. Say in chat what was merged, re-queued and asked, then continue with Step 2.

## Step 1: Prepare

1. For each repository in `repos`, run `integrate.sh init <repo> <task_name> <PROJECT_ROOT>/.mz/worktrees/<task_name>/<repo basename>`. Record `start_branch`, `start_checkout`, `integration_branch`, `worktree` and `tip` for it in state under `integration`. When the repository is a `--bg` session's worktree, `start_branch` and `start_checkout` are the branch and checkout the session left, not the worktree's own. When it prints `dirty=yes`, tell the user in one line that uncommitted edits in their checkout are not part of the run; `dirty=unknown` means the session can't see them.
1. Set `Phase: run`, `phase_complete: false`.

## Step 2: Dispatch ready units

Run `dag.sh DAG ready` and `dag.sh DAG list running`. Choose each ready unit's backend as backends.md says, in the order `ready` prints them, while a slot is free.

For each unit:

1. Its base is the current `tip` of its repository's integration worktree (`git -C <integration worktree> rev-parse HEAD`). Its branch is `orch/<task_name>/<id>` on the first attempt and `orch/<task_name>/<id>.<attempt>` on a retry, so a failed attempt's branch and worktree stay for inspection.

1. `dag.sh DAG mark <id> running base_commit=<base> branch=<branch> deadline=<now plus UNIT_DEADLINE>`.

1. Build the envelope from the unit, in the `ORCH-UNIT` format of `<PLUGIN_ROOT>/skills/orchestrate-worker/references/protocol.md`: `owns` comma-separated, `deadline` now plus `UNIT_DEADLINE`, and the unit's `spec` after `--- spec ---`. On a retry, append a `## Previous attempt` section to the spec with the last result's notes and any guidance the user gave.

1. Dispatch it on its backend, as backends.md says.

Emit the manifest first, then send every dispatch of the batch in one message:

```text
Dispatching units, batch <b> — <N> agents in parallel
Purpose: run ready units of <task_name> in their own worktrees
- <orchestrate-unit-runner | session <name> | peer <name>> — <id>: <title>
```

Don't wait for the batch. Each result arrives on its own, as a notification or a message; handle it in Step 3, then come back here, so a freed slot is filled as soon as a unit ends. When every runner of a batch has reported, emit its rollup:

```text
Wave complete (units, batch <b>) — <returned>/<dispatched> agents returned
- <worker>: <STATUS> — <id> <merged|gate|retry>
```

## Step 3: Handle a result

Take the last `ORCH-RESULT` envelope in the worker's output or message; the unit's `worktree` and `worktree_branch` are in DAG by now. When its `--- report ---` section isn't `none`, Write that text to `<TASK_DIR>/units/<id>.md`; the unit's worktree may already be gone. Output with no envelope counts as `status: FAILED` with note `no result from the worker`.

- **`DONE` or `DONE_WITH_CONCERNS`, `kind: change`.** Run `integrate.sh scope <repo> <base_commit> <branch> <owns globs…>`. Any file it prints is outside the unit's `owns`: go to Step 5 with reason `edited outside owns`. Otherwise `dag.sh DAG mark <id> done head_commit=<sha> result=<one line>` and merge it (Step 4). Keep the concerns for the final summary.
- **`DONE`, `kind: review`.** `dag.sh DAG mark <id> done result=<TASK_DIR>/units/<id>.md>`, keep the findings for the final summary, and clean up as in Step 4.
- **`FAILED`, or verify `fail`.** If `attempts` is at most `MAX_AUTO_RETRIES`, `dag.sh DAG mark <id> pending note=<one line>` and let Step 2 retry it with the failure in its spec. Otherwise Step 5 with reason `failed twice`.
- **`BLOCKED`.** Step 5 with the worker's question and options.
- **`REFUSED`.** Step 5 with the refusal reason.

A unit that ends any way but merged, and whose branch adds no commits (`git -C <repo> rev-list --count <base_commit>..<branch>` prints 0), has nothing to inspect: clean it up as in Step 4 right away. A branch with commits stays, with its worktree, for the user.

## Step 4: Merge

Merges into one repository run one at a time, in the order results arrive. Each repository has its own integration worktree; use the one for the unit's `repo`.

1. `integrate.sh merge <integration worktree> <branch> "orch merge <id>: <title>"`.
1. `state=up-to-date`: the unit added nothing. `dag.sh DAG mark <id> merged`, clean up as in 5 below, and note it.
1. Exit 3 with `conflicted=<file>` lines: dispatch `orchestrate-merge-resolver` (model: **opus**, as pinned) with the integration worktree, the conflicted files, `DAG`, the unit id, the ids of merged units whose `owns` cover those files, and their verify commands. On `DONE`, continue with 4. On anything else, `integrate.sh abort <integration worktree>` and go to Step 5 with reason `merge conflict` and the resolver's report.
1. Run the unit's `verify` in the integration worktree, as one Bash call that starts with `cd <integration worktree> &&`, and quote its last lines. A red verify: `integrate.sh abort <integration worktree>` and Step 5 with reason `red after merge`.
1. `integrate.sh conclude <integration worktree>`, record the new `tip`, `dag.sh DAG mark <id> merged`, then clean up: `integrate.sh cleanup <repo> <worktree> <branch> <integration_branch>` with the unit's `worktree` (or `none`), and `git -C <repo> branch -D <worktree_branch>` for the branch the harness made with the worktree, which the worker left behind. A `-p` worktree is left locked; cleanup unlocks it.

Then go back to Step 2.

## Step 5: The out-of-plan gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated. Units already running keep running while it waits; their results queue until it is answered.

**State**: write `awaiting approval: out-of-plan gate <id>` in `what_remains`.

**Surface 1.** Emit as a chat message:

```text
## Out of plan: <id> — <title>

Reason: <reason>
<the worker's notes, the verify output or the conflicted files, verbatim>

Downstream: <ids that depend on it, directly or not>
Still running: <ids, or none>

<output of dag.sh DAG render>

---
**Retry** — run the unit again; type guidance to send with it  ·  **Re-plan** — rewrite this unit and its dependents  ·  **Skip** — drop it and everything downstream  ·  **Abort** — dispatch nothing more, finish what runs, report
```

**Surface 2.** AskUserQuestion, question `<id> left the plan. What next?`, header `Out of plan`, options **Retry**, **Re-plan**, **Skip** and **Abort**, each with its one-line summary.

**Response handling**:

- **Retry**, or typed text, which is Retry with that text as guidance: `dag.sh DAG mark <id> pending note=<guidance>`.
- **Re-plan**: dispatch the compiler with the Phase 1 compile prompt plus `Re-plan: rewrite unit <id> and its dependents <ids> because <reason>. Keep every unit whose status is merged or done unchanged.` Lint it, run the Phase 1 review loop, and show the change as a DAG gate with the `render` output before and after. On Approve, continue; on Reject, keep the old DAG and ask this gate again.
- **Skip**: `dag.sh DAG skip <id>`; list the skipped ids in chat.
- **Abort**: set `abort: true` in state. Dispatch nothing more; handle the results of running units as usual, then finish with `Status: aborted_by_user`.
- **No answer**: this variant gate never auto-approves. Set `Status: blocked` with the unit and its question in `what_remains`, dispatch nothing more, and stop.

**Unattended** (`unattended: true`): nobody can answer, and the rest of the plan doesn't depend on this unit. Skip Surfaces 1 and 2: run `dag.sh DAG skip <id>`, then `dag.sh DAG mark <id> blocked note=<reason>`, so the unit stays visible as blocked and only its dependents are skipped. Put the unit, its reason and its question in `what_remains`, and keep dispatching.

Add a `## Lessons` line in state when the cause is one a later plan should avoid, such as a shared file left out of `owns`. Journal the gate as `<PLUGIN_ROOT>/shared/approval-gate.md` says, then go back to Step 2.

## Step 6: Finish

The run is over when `dag.sh DAG list running` and `dag.sh DAG ready` both print nothing. Show `dag.sh DAG render`, set `phase_complete: true`, and read `<SKILL_DIR>/phases/final.md`:

- After Abort, or when no change unit is `merged`, go straight to its Step 7, the report; nothing lands.
- Otherwise start at its Step 1. A fix round from its Step 5 comes back here too, and returns to Step 1 with the next `final_round`.
