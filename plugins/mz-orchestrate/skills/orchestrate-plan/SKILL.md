---
name: orchestrate-plan
description: 'Plans a goal as parallel units for /orchestrate: interview, research, a plan doc and a reviewed DAG, then runs it. Use when the user says "plan this for orchestrate" or "plan it so agents can split it". Not for an existing plan (use orchestrate).'
argument-hint: '[<goal> | @file:<brief> | resume [<task_name>]]'
allowed-tools: Agent, Skill, SendMessage, AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dag.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/shared/journal-artifact.sh *), Bash(git rev-parse *), Bash(git -C *), Bash(sha256sum *), Bash(date *), Bash(printenv MZ_DEV_PIPE_AUTO_APPROVE)
---

# Orchestrate Plan

## Overview

Turns a goal into a plan that `/orchestrate` can run without compiling it again. A short interview settles scope and acceptance, researchers read each repository in scope, and `orchestrate-planner` writes two files: a plan document with the goal, decisions, risks and open questions, and a `dag.json` whose units each carry a self-contained spec, owned paths, dependencies, a skill and a verify command. `dag.sh` lints the DAG, `orchestrate-dag-reviewer` reviews it, and the user approves plan and DAG together at one gate. That approval stands in for `/orchestrate`'s own DAG gate, so the run starts at once.

Resume pointer: after compaction, read `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`, then re-read the phase file named by its `Phase`.

## When to Use

- The user has a goal, not yet a plan, and wants it built by several workers in parallel.
- Work that spans several areas or repositories and should be cut into independent units before anyone writes code.

### When NOT to use

- A plan already exists, in a file, a `/build` plan or the conversation: run `/orchestrate` on it.
- One feature a single worker can build: `/build` plans and builds it in one run.
- A design decision that needs a reviewed ADR or RFD first: `/govern`, then this skill or `/orchestrate`.

## Input

- `<goal>`: free text, the rest of the arguments. It may name other repositories by path.
- `@file:<brief>`: a markdown file holding the goal and any constraints.
- `resume [<task_name>]`: continue a planning run that stopped. Without a name, the newest `<PROJECT_ROOT>/.mz/task/*_orchestrate-plan_*` whose `Status` is `running` or `blocked`.
- Nothing: ask in prose for the goal, since it is an open value. An empty answer stops the run.

## Constants

- **PROJECT_ROOT**: `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once in setup.
- **SKILL_DIR**: `${CLAUDE_SKILL_DIR}`; **PLUGIN_ROOT**: `${CLAUDE_PLUGIN_ROOT}`. Expand both before reading a file, running a command or writing a dispatch prompt.
- **TASK_DIR**: `<PROJECT_ROOT>/.mz/task/<task_name>/`, holding `brief.md`, `research_<n>.md`, `skills.md`, `dag.json`, `review_<n>.md` and `gate.md`.
- **PLAN_DOC**: `<PROJECT_ROOT>/.mz/design/<task_name>.md`, the plan document.
- **DAG_SH**: `<PLUGIN_ROOT>/scripts/dag.sh`. Never judge a DAG's lint result by hand.
- **SCHEMA**: `<PLUGIN_ROOT>/skills/orchestrate/references/dag-schema.md`, the unit rules the planner and the reviewer share with `/orchestrate`.
- **REGISTRY**: `<PROJECT_ROOT>/.mz/orchestrate/peers.json`, present when sessions are attached.
- **MAX_QUESTIONS**: 4 interview questions, one AskUserQuestion call. A goal that needs more is too vague to plan; ask the user to narrow it.
- **MAX_RESEARCHERS**: 4 at once. One per repository or major area keeps each researcher's context small.
- **MAX_REVIEW_ROUNDS**: 3, as in `/orchestrate`.

## Core Process

### Phase Overview

| Phase | Goal                  | Details                   | Loop                             |
| ----- | --------------------- | ------------------------- | -------------------------------- |
| 0     | Setup                 | Inline below              |                                  |
| 1     | Interview             | `phases/research_plan.md` |                                  |
| 2     | Research              | `phases/research_plan.md` |                                  |
| 3     | Plan, lint, review    | `phases/research_plan.md` | review up to `MAX_REVIEW_ROUNDS` |
| 4     | Plan gate and handoff | `phases/gate_handoff.md`  | until approved                   |

### Phase 0: Setup

1. Resolve PROJECT_ROOT and keep the printed path.
1. Parse the input as above. For `resume`, read that task's `state.md`, set `Status: running`, and go to the phase file its `Phase` names. Skip the rest of setup.
1. Name the task `<YYYY_MM_DD>_orchestrate-plan_<slug>`, where the slug is a snake_case summary of the goal, at most 20 characters. Follow `<PLUGIN_ROOT>/shared/resume-protocol.md` for an existing task of that name.
1. Run `printenv MZ_DEV_PIPE_AUTO_APPROVE` and record `unattended: true` only for the value `1`.
1. Write `state.md` with the Write tool, which creates TASK_DIR: `Phase: interview`, `Status: running`, `goal`, `unattended`, `plan: <PLAN_DOC>`, `dag: <TASK_DIR>/dag.json`.
1. Read `<SKILL_DIR>/phases/research_plan.md` and follow it. At the plan gate, read `<SKILL_DIR>/phases/gate_handoff.md`.

## Common Rationalizations

| Rationalization                                             | Rebuttal                                                                                                                                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "The goal is clear enough; I'll write the plan myself."     | "The planner reads the code and the research and writes a DAG the linter accepts. A plan from your context skips both, and /orchestrate would have to compile it again." |
| "The repository is small; I read it, so research can go."   | "Research always runs, with at least one researcher. Its report is the independent account the planner and the reviewer check the plan against."                         |
| "One researcher can cover all of it."                       | "Each repository or major area gets its own researcher, so findings come back with paths instead of a skim."                                                             |
| "The planner said lint passed."                             | "Run `dag.sh lint` yourself and quote its last line. An agent's claim is not evidence."                                                                                  |
| "The user approved the plan, so they don't need the units." | "The gate shows every unit's spec and owned paths. That approval replaces /orchestrate's DAG gate, so it has to show what /orchestrate would."                           |

## Red Flags

- Writing `dag.json` or the plan document yourself instead of through `orchestrate-planner`.
- A gate message without the rendered table and every unit's spec.
- Recording `dag_sha256` before the DAG's last lint, or changing `dag.json` after the gate.
- Asking interview questions the goal or the code already answers.
- Starting `/orchestrate` on a DAG the user didn't approve.

## Verification

Planning is done when `dag.sh <TASK_DIR>/dag.json lint` prints `lint: ok`, PLAN_DOC exists, the plan gate was answered Approve with `dag_sha256` recorded under `## Decisions`, and `/orchestrate task:<task_name>` was invoked, or the user was given that command.

## References

- `<PLUGIN_ROOT>/skills/orchestrate/references/dag-schema.md`: the `dag.json` fields and the rules for a good unit. Pass it to the planner and the reviewer.
- `<PLUGIN_ROOT>/shared/approval-gate.md`: the two-surface gate, unattended mode and the journal entry.
- `<PLUGIN_ROOT>/shared/resume-protocol.md`: the resume gate for an existing task.

## Error Handling

- No goal, or an empty answer to the prompt for one: stop with `Status: aborted_by_user`.
- A repository the goal names is not a git repository: ask for its path in prose; nobody to ask: `Status: blocked` with the path in `what_remains`.
- A researcher returns `BLOCKED` or nothing: note the gap in `brief.md` and plan without it; the planner reads the code itself.
- The planner returns `NEEDS_CONTEXT`: supply the missing path once and resume it with SendMessage; a second `NEEDS_CONTEXT` is `BLOCKED`.
- The planner returns `BLOCKED`, or `dag.json` or PLAN_DOC is missing after it returns: show its errors and stop with `Status: blocked`.
- `dag.sh` exits non-zero: show its stderr and send it to the planner once; a second failure is `BLOCKED`.
- The `/orchestrate` skill isn't available at handoff: print `/orchestrate task:<task_name>` for the user and finish.

## State Management

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase`, `Started`, `phase_complete` (boolean) and `what_remains` (YAML list of strings), with skill-specific keys below them. Milestones go in `Phase`; the reason for `blocked` or `failed` goes in `what_remains`. Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass. Refresh `what_remains` on every phase transition; it is `[]` when `Status` is `complete`. Write the file after every phase and before every gate, and re-read it after compaction. Record decisions worth recalling under a heading that reads exactly `## Decisions`, placed before `## Notes`; mz-memory harvests them only once `Status` is `complete`. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, in the form `- (review|failure|correction|change) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`. Treat a legacy `completed` as `complete`. On reading a `schema_version: 1` or unversioned file, put `schema_version: 2` on line 1 and `Status` on line 2, add the missing keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

Skill keys: `goal`, `unattended`, `repos` (absolute paths), `plan`, `dag`, `review_round`, and `dag_sha256` once the gate approves. `Phase` moves through `interview`, `research`, `plan`, `review`, `gate`, `handoff` and `done`.
