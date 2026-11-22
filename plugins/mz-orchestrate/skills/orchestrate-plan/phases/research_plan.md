# Phases 1-3: Interview, Research, Plan and Review

Expand `<PROJECT_ROOT>`, `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<TASK_DIR>` to absolute paths before every Read, command and dispatch prompt. `DAG_SH`, `SCHEMA` and `REGISTRY` are as SKILL.md defines them.

## Step 1: Interview

Agents can't see this conversation, so everything the plan rests on goes into `<TASK_DIR>/brief.md`.

1. Find the repositories. The project root is one. For every other repository the goal names, resolve the path against PROJECT_ROOT and run `git -C <path> rev-parse --show-toplevel`. Record the absolute top levels in state as `repos`.
1. Read enough to ask good questions: each repository's CLAUDE.md or README and its top-level layout. Don't ask what these answer.
1. List what the plan needs and the goal leaves open: scope (which areas, what is out), acceptance (what "done" looks like, how it is checked), hard constraints (a library, an API that must not change, a deadline order), and which repositories are involved when that is unclear.
1. When something is open, ask it in one AskUserQuestion call, at most MAX_QUESTIONS questions, header `Scope`, `Done when`, `Limits` or `Repos`. Each question offers two to four concrete options drawn from the code, the most likely first; the user types anything else. This is an input collector, not a gate: no plan message before it.
1. Nothing open: skip the call and say in one line that the goal settles scope and acceptance.

Write `brief.md`: the goal verbatim, then `## Answers` with each question and answer, `## Repositories`, and `## Assumptions` for anything still open, which the planner lists as an open question.

**Unattended** (`unattended: true`) or no AskUserQuestion in your tool list: skip the call, put every open point under `## Assumptions` with the most likely option, and go on.

Set `Phase: research` in state.

## Step 2: Research

Research runs on every goal, however small the repository: at least one researcher, even when you have read the code yourself. Its report is what the planner and the reviewer check the plan against. Pick the areas: one per repository in scope, or, in a single large repository, one per major area the goal touches, at most MAX_RESEARCHERS. Emit the manifest, then send every dispatch in one message:

```text
Dispatching researchers — <N> agents in parallel
Purpose: map the code the plan for <task_name> will change
- pipeline-researcher — <area>
```

Each `pipeline-researcher` (model as pinned) gets:

```text
Research for a plan that parallel workers will carry out.

Goal and answers: <TASK_DIR>/brief.md
Area: <repository path, and the directories of this area>

Report: the files and modules the goal touches, with paths; the conventions a change there must follow; how this area is tested, with the exact test command and where tests live; shared files that several changes would have to edit (registries, routers, schemas, config); and risks. Name paths, not summaries.
```

The researcher returns its report as text. Write each one to `<TASK_DIR>/research_<n>.md` with the Write tool. When every researcher has returned, emit the rollup:

```text
Wave complete (research) — <returned>/<dispatched> agents returned
- pipeline-researcher: <STATUS> — <area>
```

Set `Phase: plan` in state.

## Step 3: Catalog the skills

Write `<TASK_DIR>/skills.md` from this session's own skill listing, so units go only to skills that are installed. One line per skill that is present: `<plugin:skill> — <its description>`, for `mz-dev-pipe:build`, `mz-dev-pipe:debug`, `mz-dev-pipe:polish` and `mz-creative:document` (change skills that accept a `unit:` brief), and `mz-dev-git:review-branch` and `mz-dev-pipe:audit` (review skills). Add `direct — the worker makes a small mechanical edit itself` as the last line.

## Step 4: Plan

Dispatch `orchestrate-planner` (model: **opus**, as pinned):

```text
Plan this goal for parallel workers and write its DAG.

Schema: <SCHEMA>
Brief: <TASK_DIR>/brief.md
Research: <TASK_DIR>/research_1.md … research_<n>.md
Skill catalog: <TASK_DIR>/skills.md
Peer registry: <REGISTRY, or "none">
Project: <PROJECT_ROOT>
Repositories: <repos, one per line>
Task: <task_name>
dag.sh: <DAG_SH>

Write the plan document to <PLAN_DOC> and the DAG to <TASK_DIR>/dag.json.
```

When it returns, check that both files exist, then run `<DAG_SH> <TASK_DIR>/dag.json lint` (add the REGISTRY path when it exists) and quote its last line. A failing lint goes back to the planner once, with the errors pasted into a SendMessage. Handle its `STATUS:` as SKILL.md's Error Handling says, and keep `DONE_WITH_CONCERNS` notes for the gate.

## Step 5: Review loop

Set `Phase: review` and `review_round: 1`.

1. Dispatch `orchestrate-dag-reviewer` (model: **sonnet**, as pinned):

   ```text
   Review the planned DAG, round <n>.

   Schema: <SCHEMA>
   Source plan: <PLAN_DOC>
   DAG: <TASK_DIR>/dag.json
   Compiler notes: <TASK_DIR>/brief.md
   Skill catalog: <TASK_DIR>/skills.md

   Write the review to <TASK_DIR>/review_<n>.md.
   ```

1. Check that the review file exists and take its last `VERDICT:` line.

1. `VERDICT: PASS`: go to the plan gate.

1. `VERDICT: FAIL` below MAX_REVIEW_ROUNDS: resume the planner with SendMessage, or dispatch it again with the Step 4 prompt plus `Revision round: fix the findings in <TASK_DIR>/review_<n>.md.` Lint again as in Step 4, add 1 to `review_round`, and repeat from 1.

1. `VERDICT: FAIL` at MAX_REVIEW_ROUNDS: go to the plan gate and show the remaining `Critical:` findings there.

When a finding is accepted and fixed, add a `- (review) WHEN … → … — WHY …` line under `## Lessons` in state for findings a later plan should avoid.

Then read `<SKILL_DIR>/phases/gate_handoff.md`.
