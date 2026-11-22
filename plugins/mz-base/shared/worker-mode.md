# Worker Mode

mz-orchestrate runs one unit of an approved plan by invoking a skill with a `unit:<path>` token. The user already approved the whole plan at the orchestrator's DAG gate, and nobody is watching this run. Skills that support worker mode (`build`, `debug`, `polish`, `document`) follow this file whenever the token is present.

## Unit brief

The path, absolute or relative to the project root, points to a markdown file that the orchestrator wrote:

```markdown
# Unit <id>: <title>

- task: <orchestrator task name>
- kind: change
- skill: <plugin>:<skill>
- owns: <glob>, <glob>
- verify: <command>

## Spec

<self-contained brief: what to build or fix, acceptance criteria, context from finished dependencies>
```

The `## Spec` section is the skill's task description. Other text in the arguments is ignored.

## Setup

- Derive the task name from the unit id (`<YYYY_MM_DD>_<skill>_<id-slug>`) and start fresh. A `_vN` is fine, but there is no resume gate: the orchestrator retries a unit with a new worker.
- Record `worker_unit: <path>` and `unattended: worker` in `state.md`. Skip the `MZ_DEV_PIPE_AUTO_APPROVE` check, since worker mode already decides every gate.
- Skip any input-collection question. A missing or empty spec is a blocker.
- Write `state.md` with the Write tool before the first phase starts, and keep it updated as the skill says.

## Pipeline

Worker mode changes who answers the gates, nothing else. Run every phase the skill defines and dispatch every agent it names, even for a small unit. The orchestrator chose this skill for its tests, reviews and checks, and the user approved the plan on the understanding that they would run. Doing the work inline skips the reviews that a merge relies on. If a phase truly doesn't apply, such as no linter detected, say so in the final message the way the skill already does.

## Gates

- **Approve/Reject gates** (plan, diagnosis, assessment, research): write state, emit Surface 1, skip Surface 2 and continue as on Approve. Log the gate the way unattended mode does, in chat, under `## Auto-approvals`, in the journal and in the final report, with `outcome: auto-approved (worker)` and `authority: mz-orchestrate DAG gate, unit <id>`.
- **Everything else that would ask the user** is a blocker: variant gates, cap-reached menus, "can't reproduce", "no test framework", a scope that matches no files. Never call AskUserQuestion in worker mode. Finish the work that doesn't depend on the answer, write the question and its options to `state.md`, set `Status: blocked`, and end as below with `STATUS: BLOCKED`.

## Scope

- Edits stay inside the brief's `owns` globs. Pass the globs to every agent that writes files, as a hard constraint.
- When the work truly needs a file outside `owns`, make the smallest edit and name the file and the reason under `## Concerns`, which makes the result `DONE_WITH_CONCERNS`. If the edit would be large, stop with `STATUS: BLOCKED` instead.
- Don't commit, push, switch branches or create worktrees. The worker that invoked the skill commits the result.

## Final message

End with the skill's usual verification block, then these sections when they apply, then the status line as the very last line:

- `## Files changed`: one path per line.
- `## Verify`: the brief's `verify` command and its result (pass, fail, or not run and why).
- `## Concerns` or `## Blocker`: as in the status protocol.
- `STATUS: DONE`, `STATUS: DONE_WITH_CONCERNS` or `STATUS: BLOCKED`.
