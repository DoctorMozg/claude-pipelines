# Phase 4: Plan Gate and Handoff

Expand `<PROJECT_ROOT>`, `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<TASK_DIR>` to absolute paths before every Read, command and dispatch prompt.

This gate approves the plan and its DAG together. `/orchestrate` accepts that approval in place of its own DAG gate, so the gate shows everything its DAG gate would.

## Step 1: Build the gate

Write `<TASK_DIR>/gate.md`:

```markdown
# Plan for <task_name>

<verbatim contents of PLAN_DOC>

## Unit graph

<output of dag.sh <TASK_DIR>/dag.json render>

## Units

### <id>: <title>
- kind / skill / backend: <kind> / <skill> / <backend>
- repo: <repo>
- owns: <owns>
- verify: `<verify>`
- depends on: <depends_on, or none>

<spec>

(one block per unit, in DAG order)

## Unresolved review findings
<the Critical findings of the last review if it failed, or "none">

## Cost
Planning so far: <researchers> researchers, the planner and <review_round> review rounds. Running it: <units per skill>. Each build, debug and polish unit runs that skill's full pipeline of agents; rough cost per unit on small units: build about $2.50, debug about $1, polish about $0.50, review about $1, direct about $0.20.
```

## Step 2: The plan gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<TASK_DIR>/gate.md` and capture its full contents.
**State**: `Phase: gate`, `phase_complete: false`, and `awaiting approval: plan gate` in `what_remains`.

**Surface 1: emit the plan message.** Output the contents verbatim as a chat message:

```text
## Plan for review: orchestrate-plan

<verbatim contents of <TASK_DIR>/gate.md>

---
**Approve** → /orchestrate runs these units now, with no second DAG gate  ·  **Reject** → stop; nothing runs  ·  reply with feedback to revise
```

Emit `gate.md` as written, every unit block included: never a path, a summary or your own rewording of it.

**Surface 2: call AskUserQuestion.** question: "The plan and its DAG above are ready for review." header: "Plan gate". Options: **Approve** — run these units with /orchestrate · **Reject** — stop without running anything. When AskUserQuestion isn't in your tool list, as in a headless run, that is **No answer** below: set `Status: blocked`, and end the turn with this line in place of any request for a typed approval: `Blocked at the plan gate. Run /orchestrate-plan resume <task_name> in an interactive session to answer it.` A typed approval can't be recorded; only this gate records one.

**Response handling**:

- **Approve** → run `sha256sum <TASK_DIR>/dag.json`, record `dag_sha256: <hash>` in state and `- Plan approved: <PLAN_DOC>, dag.json sha256 <hash> (<N> units), <UTC date>` under `## Decisions`, clear `awaiting approval`, set `phase_complete: true`, and go to Step 3.
- **Reject** → set `Status: aborted_by_user` and stop. PLAN_DOC and `dag.json` stay for the user.
- **Any other answer** is feedback. Resume the planner with the feedback verbatim (or dispatch it again with the Step 4 prompt of `research_plan.md` plus `Revision: apply this feedback from the user: <feedback>`), lint, run the review loop from round 1, rebuild `gate.md`, and return to Surface 1 with the whole message. When the feedback corrects a mistake rather than a preference, add a `(correction)` line under `## Lessons`. Loop until Approve.
- **No answer** → set `Status: blocked` with `awaiting approval: plan gate`, and stop. A missing answer is never approval.

**Unattended** (`unattended: true`): emit Surface 1, skip Surface 2, record the hash as for Approve, and log the auto-approval as `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode", says.

**Journal.** After the gate resolves, append the entry that `<PLUGIN_ROOT>/shared/approval-gate.md`, "Journal entry", describes to `<PROJECT_ROOT>/.mz/journal.md`, with `<PLUGIN_ROOT>/shared/journal-artifact.sh <TASK_DIR>/gate.md <PROJECT_ROOT>/.mz/journal.md` for the artifact.

## Step 3: Hand off to /orchestrate

1. Set `Phase: done`, `Status: complete`, `what_remains: []` in state, so this task is finished before the run begins.
1. Say in one line that the plan is at PLAN_DOC and that `/orchestrate` takes over.
1. Invoke `mz-orchestrate:orchestrate` with the Skill tool and the argument `task:<task_name>`. It checks that `dag.json` still has the approved hash, lints it against the peers attached now, and starts running units.

When the Skill call isn't possible, print `/orchestrate task:<task_name>` for the user instead. Don't change `dag.json` after the gate: `/orchestrate` would see a different hash and show its own DAG gate.
