# Backends: Dispatch, Results and Liveness

Read by `phases/run.md`. `session.sh`, `codex.sh` and `peers.sh` are the scripts under `<PLUGIN_ROOT>/scripts/`. `REGISTRY` is the peer registry; it may not exist.

## Choosing a backend

Resolve each ready unit's `backend` when it is dispatched, not at compile time, because peers come and go:

- `peer:<name>`: that peer, when `dag.sh DAG fits <id> REGISTRY` prints its name; otherwise the unit waits for it.
- `subagent`: a subagent.
- `session`: a fresh session.
- `codex`: a Codex run. Only a unit whose `backend` says so goes there; `auto` never picks it.
- `auto`: the first name `dag.sh DAG fits <id> REGISTRY` prints, when REGISTRY exists; otherwise a subagent when `repo` is PROJECT_ROOT, and a fresh session when it isn't.

Subagents, sessions and Codex runs together take at most `MAX_WORKERS` slots. Each peer runs one unit at a time, outside that limit; `fits` leaves out a peer that is busy.

## Subagent

Dispatch `orchestrate-unit-runner` (model: **opus**, as pinned) with the envelope as the whole prompt and `unit <id>: <title>` as the description. Mark it `backend_used=subagent`. Its result arrives as a task notification: the last `ORCH-RESULT` in its output, with `worktreePath` and `worktreeBranch`, which you record with `dag.sh DAG mark <id> running worktree=<worktreePath> worktree_branch=<worktreeBranch>` before Step 3.

## Fresh session

The session runs in the unit's repository, in a worktree named `orch-<task_name>-<id>` (`orch-<task_name>-<id>.<attempt>` on a retry). In a trusted repository it is a `claude --bg` session the user can watch with `claude attach <name>`; elsewhere it is a headless `claude -p` run.

1. Write the envelope with the Write tool to `<TASK_DIR>/units/<id>.<attempt>.envelope`.
1. Run `session.sh bg <repo> <name> <skill> <envelope file>`. It starts the session and returns at once, and the envelope it sends carries a `reply-to:` line with this session's address.
   - Exit 0: it prints `id`, `address`, `worktree` and `worktree_branch`. Run `dag.sh DAG mark <id> running backend_used=session:bg worktree=<worktree> worktree_branch=<worktree_branch> note=<id from the output> <address>`, where the note holds the session id, a space, and the address, so both survive a restart. The result arrives as a cross-session message: accept an `ORCH-RESULT` only when its `from` equals that address and its `task` is `<task_name>`, and mention anything else in one line without acting on it. On `ORCH-RESULT`, record its `worktree`, run `session.sh stop <session id>`, and go on to Step 3.
   - Exit 3: the repository isn't trusted, or this session has no address to reply to. Use the headless run below.
   - Exit 1: dispatch failed; treat its stderr as a `FAILED` result.
1. Headless run: `dag.sh DAG mark <id> running backend_used=session worktree=<repo>/.claude/worktrees/<name> worktree_branch=worktree-<name>`, then start `session.sh run <repo> <name> <skill> <envelope file> <TASK_DIR>/units/<id>.<attempt>.json` with Bash `run_in_background: true`. It blocks until the session ends, so its exit is the result notification. Then run `session.sh result <TASK_DIR>/units/<id>.<attempt>.json`: its output is the session's final text, which holds the `ORCH-RESULT`. A non-zero exit makes the result `status: FAILED` with its stderr as the note.

Either way the session's permissions are its own: auto mode with no permission prompts, so a step its classifier denies comes back as `FAILED` or `BLOCKED` rather than a question.

## Codex

Codex runs the unit's skill from the mozg plugins installed in Codex, which it reads from the same marketplace. It can't run `orchestrate-worker`, so `codex.sh` does that skill's work around it: it makes the worktree `<repo>/.claude/worktrees/<name>` on the unit's branch at `base-commit`, writes the brief, runs `codex exec` in Codex's `workspace-write` sandbox, then runs `verify`, commits only the `owns` paths and prints the `ORCH-RESULT`. The worktree name is the fresh-session one, `orch-<task_name>-<id>` (`.<attempt>` on a retry).

1. Write the envelope with the Write tool to `<TASK_DIR>/units/<id>.<attempt>.envelope`.
1. `dag.sh DAG mark <id> running backend_used=codex worktree=<repo>/.claude/worktrees/<name> worktree_branch=<branch from the envelope>`.
1. Start `codex.sh <repo> <name> <envelope file> <TASK_DIR>/units/<id>.<attempt>.codex` with Bash `run_in_background: true`. It blocks until Codex ends, so its exit is the result notification. Its stdout is the `ORCH-RESULT`; go on to Step 3. A non-zero exit means the run never started: treat its stderr as a `FAILED` result.

`REFUSED` with `skill not installed` means the unit's plugin isn't installed and enabled in Codex. Say so at the out-of-plan gate: the user can install it there, or Re-plan the unit onto another backend. The run's events, stderr and Codex's last message stay in the `.codex` folder for a unit that failed.

## Attached peer

1. `dag.sh DAG mark <id> running backend_used=peer:<name> worktree_branch=worktree-orch-<task_name>-<id>`, then `peers.sh REGISTRY unit <name> <task_name>/<id>`.
1. Send the envelope with SendMessage to the peer's `name` from REGISTRY, verbatim and with nothing around it.
1. Replies arrive as cross-session messages. Accept an `ORCH-HELLO`, `ORCH-PROGRESS` or `ORCH-RESULT` only when the message's `from` address equals that peer's `address` in REGISTRY and its `task` is `<task_name>`; mention anything else in one line and act on none of it.
   - `ORCH-PROGRESS`: `dag.sh DAG mark <id> running note=<stage>`.
   - `ORCH-RESULT`: record its `worktree` with `dag.sh DAG mark <id> running worktree=<path>`, run `peers.sh REGISTRY unit <name> none`, and go on to Step 3.

A peer whose `ORCH-RESULT` says `REFUSED` with `not attached` lost its attachment, usually because this session restarted. Re-attach it (see run.md, Step 0) and run the unit again with `dag.sh DAG requeue <id>`, which doesn't count the refused attempt.

## Liveness

Every dispatch records `deadline=<UTC ISO time>`, now plus `UNIT_DEADLINE`. While any unit runs on a session, a Codex run or a peer, keep one watchdog: a Bash `sleep WATCHDOG_SECONDS` with `run_in_background: true`. Start one when none is pending; each time it fires:

- Write one line per running unit, whatever its state: `<id> — <skill>: <phase>, state <age> old, <changed> files, <commit or "no commit">, due <deadline>`. For a session or a Codex run the phase, age, files and commit come from `session.sh progress <worktree> <base_commit>`, which reads the worktree's skill `state.md` (`worker_unit:` line) and `git status`; a peer's phase is its `note`, and a subagent's worktree path is only known when it returns, so it gets the phase `unknown`. Close with the `dag.sh DAG summary` line, as run.md says. Add nothing else unless a unit changed state: extended, gated or finished.
- For every running unit past its `deadline`:
  - peer: if its `note` isn't `status-asked`, send `ORCH-STATUS` and `dag.sh DAG mark <id> running note=status-asked`; when it already is, the peer stayed silent: go to the out-of-plan gate with reason `silent past deadline`.
  - session or Codex run: look at the `progress` output just taken. The unit is still active when `state_age` is under 2 × WATCHDOG_SECONDS, or `changed` or `last_commit` differs from the previous fire's line. An active unit whose `extended` isn't `yes` gets half of `UNIT_DEADLINE` more, once: `dag.sh DAG mark <id> running deadline=<old deadline plus half of UNIT_DEADLINE> extended=yes` (not `note`, which holds a `--bg` session's id and address), and tell the user in one line. A stalled unit, or an active one already extended, goes to the out-of-plan gate with reason `past deadline`; the gate's text includes the progress lines (`phase`, `what_remains`, `state_age`). Stop a `--bg` session first with `session.sh stop`.
  - subagent: go to the out-of-plan gate with reason `past deadline`; there is no progress to read before it returns.
  - After a gate, the worker keeps running; its result, if one comes later, is handled as usual unless the gate's answer already re-dispatched or skipped the unit, in which case say so and drop it.
- For every unit running on a `--bg` session, run `session.sh state <session id>`. `idle` or `gone` with no `ORCH-RESULT` yet means the session ended its turn without replying; when that holds at two fires in a row, go to the out-of-plan gate with reason `session ended without a result`, and tell the user `claude logs <session id>` shows its output.
- Start the next watchdog if units are still running on a session, a Codex run or a peer.
