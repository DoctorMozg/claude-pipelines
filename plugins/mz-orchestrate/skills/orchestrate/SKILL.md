---
name: orchestrate
description: 'Runs an approved plan as parallel units on workers in their own worktrees. Use when the user says "orchestrate this plan" or "split this across agents", or hands over a plan.md or design doc to execute. Not for making the plan (use orchestrate-plan).'
argument-hint: '[<plan file> | task:<task_name> | this plan | resume [<task_name>]]'
allowed-tools: Agent, Skill, SendMessage, ListAgents, AskUserQuestion, EnterWorktree, Read, Write, Edit, Glob, Grep, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dag.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/integrate.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/session.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/codex.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/peers.sh *), Bash(sleep *), Bash(${CLAUDE_PLUGIN_ROOT}/shared/journal-artifact.sh *), Bash(git rev-parse *), Bash(git -C *), Bash(sha256sum *), Bash(mkdir *), Bash(date *), Bash(printenv MZ_DEV_PIPE_AUTO_APPROVE)
---

# Orchestrate

## Overview

Takes a plan that is already settled, from a conversation, `/govern`, `/build`'s planner, a design doc or any markdown file, and turns it into a DAG of units: each with its own spec, owned paths, dependencies, skill and verify command. The DAG is linted by a script, reviewed by an agent, and shown to the user once. After that approval the user is asked again only when something leaves the plan.

Each unit runs in its own git worktree through the mozg skill that fits it, on a subagent, a fresh session (`claude --bg` in a trusted repository, `claude -p` otherwise), an attached peer session, or Codex when the plan names it, in any repository the plan names. It is merged into that repository's integration branch, `orchestrate/<task>`, once its verify passes on the merged tree. When every unit is in, each integration branch gets its full suite and a review, and the user's branch moves only at the final gate, by fast-forward, never pushed. A restarted run picks up where the old one stopped and runs nothing twice.

Resume pointer: after compaction, read `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`, then re-read the phase file named by its `Phase`.

## When to Use

- The user has a plan and wants it carried out by several workers in parallel.
- A build `plan.md`, an ADR, an RFD or a design doc should become running work without re-planning.

### When NOT to use

- No plan yet: `/orchestrate-plan` plans the goal and hands the plan back here; `/govern`, a design doc or the conversation work too.
- One small change: run `/build` or `/debug` directly; orchestration costs a compile, a review and a gate.
- Attaching or releasing worker sessions: `/orchestrate-attach`, `/orchestrate-detach`.

## Input

- `<plan file>`: any markdown file. Its shape decides `source.kind`: a `## Work Units` section with `### WU-N` headings is a `build-plan`; MADR frontmatter with `## Decision Outcome` is an `adr`; an RFD, or a doc with `## The actual design` or `## Milestones`, is a `design`; anything else is `markdown`.
- `task:<task_name>`: a task in `<PROJECT_ROOT>/.mz/task/<task_name>/`. One from `/orchestrate-plan`, whose `state.md` has `dag_sha256`, brings its approved `dag.json` and plan document, `source.kind: orchestrate-plan`; any other brings its `plan.md`, as a `build-plan`.
- Nothing, "this plan" or "the plan above": the plan in the current conversation, `source.kind: conversation`.
- `resume [<task_name>]`: continue an orchestration that stopped, such as after the session was closed. Without a name, the newest `<PROJECT_ROOT>/.mz/task/*_orchestrate_*` or `<PROJECT_ROOT>/.claude/worktrees/*/.mz/task/*_orchestrate_*`, where a `--bg` run keeps it, whose `Status` is `running` or `blocked`; TASK_DIR is wherever it was found. Saying `resume` answers the resume gate, so it isn't shown.

A path that doesn't exist is reported, and the skill asks for the right one in plain prose.

## Constants

- **PROJECT_ROOT**: `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once in setup.
- **SKILL_DIR**: `${CLAUDE_SKILL_DIR}`; **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`. Expand both before reading a file, running a command or writing a dispatch prompt.
- **TASK_DIR**: `<PROJECT_ROOT>/.mz/task/<task_name>/`, holding `source_plan.md`, `skills.md`, `dag.json`, `compile_notes.md`, `review_<n>.md` and `gate.md`.
- **DAG_SH**: `<PLUGIN_ROOT>/scripts/dag.sh`, the only writer of `dag.json` after the compiler. Never compute the ready set, a lint result or a status by hand.
- **REGISTRY**: `<PROJECT_ROOT>/.mz/orchestrate/peers.json`, present when sessions are attached.
- **MAX_REVIEW_ROUNDS**: 3. A DAG that still fails review after three revisions has a problem the user should see.
- **INTEGRATE_SH**: `<PLUGIN_ROOT>/scripts/integrate.sh`, which does every git step on the integration and unit branches.
- **MAX_WORKERS**: 3 units at once. Each worker runs a skill that dispatches about 6 agents of its own, and a session runs at most 20 subagents.
- **MAX_FINAL_ROUNDS**: 2. The final review runs at most twice, so one round of fixes is checked before the final gate.
- **CHECKPOINT_EVERY**: 3 merges into one repository between full-suite checkpoints, so a unit that breaks another unit's tests is found a few merges later, not at the end.
- **MAX_AUTO_RETRIES**: 1. A unit that fails is retried once with its failure in the spec; a second failure goes to the user.
- **UNIT_DEADLINE**: 45 minutes, written into each envelope and into DAG.
- **WATCHDOG_SECONDS**: 600, how often a silent run is checked while units run on sessions or peers.

## Core Process

### Phase Overview

| Phase | Goal                           | Details                               | Loop                                |
| ----- | ------------------------------ | ------------------------------------- | ----------------------------------- |
| 0     | Setup                          | Inline below                          |                                     |
| 1     | Ingest and compile             | `phases/plan.md`                      | review up to `MAX_REVIEW_ROUNDS`    |
| 1.5   | DAG gate                       | `phases/plan.md`                      | until approved                      |
| 2     | Run, merge, verify, checkpoint | `phases/run.md`, `phases/backends.md` | until nothing is ready or running   |
| 3     | Final review, gate             | `phases/final.md`                     | fix rounds up to `MAX_FINAL_ROUNDS` |

### Phase 0: Setup

1. Resolve PROJECT_ROOT and keep the printed path.
1. Parse the input as above and record the source path and kind. For `resume`, read that task's `state.md`, set `Status: running`, and go straight to the phase file its `Phase` names; for `Phase: run`, start at run.md's Step 0, and for `Phase: final`, at final.md's Step 1. Skip the rest of setup.
1. Name the task `<YYYY_MM_DD>_orchestrate_<slug>`, where the slug is a snake_case summary of the plan, at most 20 characters. Follow `<PLUGIN_ROOT>/shared/resume-protocol.md` for an existing task of that name.
1. Run `printenv MZ_DEV_PIPE_AUTO_APPROVE` and record `unattended: true` only for the value `1`.
1. Write `state.md` with the Write tool, which creates TASK_DIR: `Phase: ingest`, `Status: running`, the source keys, `unattended`, `dag: <TASK_DIR>/dag.json`. In a `claude --bg` session this Write is refused until the session isolates: call EnterWorktree with `name: orchestrate-<slug>`, resolve PROJECT_ROOT again inside it, and write there. From then on, name this repository by the worktree path, because `git -C` into the checkout the session left is refused; `integrate.sh init` still finds the user's branch.
1. Read `<SKILL_DIR>/phases/plan.md` and follow it.

After the DAG gate approves, set `Phase: run` and read `<SKILL_DIR>/phases/run.md`. When nothing is ready or running, run.md hands over to `<SKILL_DIR>/phases/final.md`, which checks each integration branch, holds the final gate and writes the report.

## Common Rationalizations

| Rationalization                                                    | Rebuttal                                                                                                                                               |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "The compiler said lint passed, so I'll skip running it."          | "An agent's claim is not evidence. Run `dag.sh lint` yourself and quote its last line."                                                                |
| "I can see which units are ready."                                 | "Ready sets, skips and statuses come from `dag.sh`. A hand-computed set drifts from `dag.json`, which is the one source of truth."                     |
| "The change is tiny; I'll run the tests and read the diff myself." | "The final phase's suite runs through the test runner and its review is a unit. Your own reading is not the independent check the final gate reports." |
| "The plan is clear, the gate can show a summary."                  | "The gate shows `gate.md` verbatim. The user approves what every worker will do; a summary hides the specs and owned paths."                           |

## Red Flags

- Editing `dag.json` by hand after compile instead of through the compiler or `dag.sh`.
- A gate message without the rendered table and graph.
- Starting compile with the conversation's plan held only in memory, not written to `source_plan.md`.
- Fixing a unit's code yourself after a worker failed, instead of the out-of-plan gate.
- A final gate whose suite or review didn't come from the test runner and a review unit.
- Merging a unit whose verify was not run on the merged tree, or running `git` on the integration branch by hand instead of through INTEGRATE_SH.

## Verification

Compile is done when `dag.sh <TASK_DIR>/dag.json lint` prints `lint: ok` and the DAG gate was answered Approve, or an `/orchestrate-plan` approval was accepted, recorded under `## Decisions`. The run is done when `dag.sh … list running` and `dag.sh … ready` print nothing, every change unit is `merged` or `skipped`, and each merge's verify output was quoted. The orchestration is done when the final gate was answered, each repository has a `landed` value, and `<PROJECT_ROOT>/.mz/reports/<task_name>.md` exists.

## References

- `${CLAUDE_SKILL_DIR}/references/dag-schema.md`: the `dag.json` fields and the rules for a good unit. Pass it to the compiler and the reviewer.
- `<PLUGIN_ROOT>/shared/approval-gate.md`: the two-surface gate, unattended mode and the journal entry.
- `<PLUGIN_ROOT>/shared/resume-protocol.md`: the resume gate for an existing task.
- `<PLUGIN_ROOT>/skills/orchestrate-worker/references/protocol.md`: the `ORCH-UNIT` and `ORCH-RESULT` envelopes the run builds and reads.

## Error Handling

- The plan file is missing or empty: say so and ask for the path in prose. Nobody to ask: `Status: blocked`.
- The conversation holds no plan: ask the user to paste it or name a file, and stop.
- A repository the plan names is not a git repository: ask for its path; nobody to ask: `Status: blocked` with the path in `what_remains`.
- The compiler returns `NEEDS_CONTEXT`: supply the missing path once and resume it with SendMessage; a second `NEEDS_CONTEXT` is `BLOCKED`.
- The compiler returns `BLOCKED`, or `dag.json` is missing after it returns: show its errors and stop with `Status: blocked`.
- `dag.sh` exits non-zero: show its stderr. It never leaves a half-written `dag.json`.
- `integrate.sh` exits 1: show its stderr and stop dispatching; the integration worktree keeps whatever state the message names.
- A unit runner fails with an API error or a usage limit: mark the unit `failed` with the cause and go to the out-of-plan gate; re-dispatching doesn't fix an exhausted quota.

## State Management

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase`, `Started`, `phase_complete` (boolean) and `what_remains` (YAML list of strings), with skill-specific keys below them. Milestones go in `Phase`; the reason for `blocked` or `failed` goes in `what_remains`. Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass. Refresh `what_remains` on every phase transition; it is `[]` when `Status` is `complete`. Write the file after every phase and before every gate, and re-read it after compaction. Record decisions worth recalling under a heading that reads exactly `## Decisions`, placed before `## Notes`; mz-memory harvests them only once `Status` is `complete`. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, in the form `- (review|failure|correction|change) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`. Treat a legacy `completed` as `complete`. On reading a `schema_version: 1` or unversioned file, put `schema_version: 2` on line 1 and `Status` on line 2, add the missing keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

Skill keys: `source` (original path, or `conversation`), `source_kind`, `source_sha256`, `plan_approved` (for an `/orchestrate-plan` task), `repos` (absolute paths), `dag`, `review_round`, `unattended`, `integration` (per repository: `start_branch`, `start_checkout`, `integration_branch`, `worktree`, `tip`, and `landed`: a commit, `user` or `no`), `final_round` and `abort`. `Phase` moves through `ingest`, `compile`, `review`, `gate`, `run`, `final` and `done`; a fix round goes from `final` back to `run`. Unit statuses live only in `dag.json`.
