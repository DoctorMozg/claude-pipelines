# Phase 1: Ingest, Compile, Review and the DAG Gate

Expand `<PROJECT_ROOT>`, `<SKILL_DIR>`, `<PLUGIN_ROOT>` and `<TASK_DIR>` to absolute paths before every Read, command and dispatch prompt.

## Step 1: Ingest the plan

The compiler can't see this conversation, so the plan it compiles is always a file in TASK_DIR.

- **Conversation.** Write `<TASK_DIR>/source_plan.md` with the Write tool: the plan as the user settled it, quoted verbatim where the thread holds its text, followed by a `## Decisions from the conversation` section listing every choice the user made about it. Don't add work, and don't smooth over a question that was left open: list it under `## Open questions`. Tell the user the path in one line, so they can correct it at the gate.
- **File.** Read it and write the same contents to `<TASK_DIR>/source_plan.md`. Record its original path and `sha256sum <path>` in state.
- **An `/orchestrate-plan` task.** Read its `state.md` and run `sha256sum` on its `dag.json`. Write its plan document (the `plan` key) to `<TASK_DIR>/source_plan.md` and its `dag.json`, read and written back unchanged, to `<TASK_DIR>/dag.json`. Record `source` as the plan document, `source_kind: orchestrate-plan`, and `plan_approved: yes` when the hash equals its `dag_sha256`, `no` otherwise. Take `repos` from its state.

Then find the repositories. The project root is one. For every other repository the plan names, resolve the path against PROJECT_ROOT and run `git -C <path> rev-parse --show-toplevel`. Record the absolute top levels in state as `repos`.

## Step 2: Catalog the skills

Write `<TASK_DIR>/skills.md` from this session's own skill listing, so units go only to skills that are installed. One line per skill that is present: `<plugin:skill> — <its description>`, for these:

- `mz-dev-pipe:build`, `mz-dev-pipe:debug`, `mz-dev-pipe:polish`, `mz-creative:document`: change skills that accept a `unit:` brief.
- `mz-dev-git:review-branch`, `mz-dev-pipe:audit`: review skills.

Add `direct — the worker makes a small mechanical edit itself` as the last line. When none of the change skills is installed, say so: every change unit will be `direct`, and the user should install mz-dev-pipe first.

Set `Phase: compile` in state.

## Step 3: Compile

For an `/orchestrate-plan` task, the DAG is already built: run `<PLUGIN_ROOT>/scripts/dag.sh <TASK_DIR>/dag.json lint` (add the REGISTRY path when it exists) and quote its last line. With `plan_approved: yes` and `lint: ok`, the user approved this DAG at the plan gate: add `- DAG approved at the plan gate of <plan task>: <TASK_DIR>/dag.json (<N> units), <UTC date>` under `## Decisions`, say so in one line, and go on to Phase 2 as SKILL.md says, with no review and no DAG gate. Otherwise say what changed (the hash, or the lint errors, which may come from peers attached since), dispatch the compiler with the prompt below plus `Revision: dag.json came from /orchestrate-plan and <changed since its plan gate | fails lint: <errors>>. Edit it rather than recompiling.`, and carry on from there as for any compile, review and DAG gate included.

Otherwise, dispatch `orchestrate-plan-compiler` (model: **opus**, as pinned) with this prompt:

```text
Compile the source plan into an orchestration DAG.

Schema: <SKILL_DIR>/references/dag-schema.md
Source plan: <TASK_DIR>/source_plan.md (kind: <source_kind>)
Skill catalog: <TASK_DIR>/skills.md
Peer registry: <REGISTRY, or "none">
Project: <PROJECT_ROOT>
Repositories: <repos, one per line>
Task: <task_name>
dag.sh: <PLUGIN_ROOT>/scripts/dag.sh

Write the DAG to <TASK_DIR>/dag.json and your notes to <TASK_DIR>/compile_notes.md.
```

When it returns, check that `dag.json` exists, then run `<PLUGIN_ROOT>/scripts/dag.sh <TASK_DIR>/dag.json lint` (add the REGISTRY path when it exists) and quote its last line. A failing lint goes back to the compiler once, with the errors pasted into a SendMessage; a second failure ends the run as `BLOCKED` with the errors.

Handle the compiler's `STATUS:` as the Error Handling section in SKILL.md says. Keep its `DONE_WITH_CONCERNS` notes for the gate.

## Step 4: Review loop

Set `Phase: review` and `review_round: 1`.

1. Dispatch `orchestrate-dag-reviewer` (model: **sonnet**, as pinned):

   ```text
   Review the compiled DAG, round <n>.

   Schema: <SKILL_DIR>/references/dag-schema.md
   Source plan: <TASK_DIR>/source_plan.md
   DAG: <TASK_DIR>/dag.json
   Compiler notes: <TASK_DIR>/compile_notes.md
   Skill catalog: <TASK_DIR>/skills.md

   Write the review to <TASK_DIR>/review_<n>.md.
   ```

1. Check that the review file exists and take its last `VERDICT:` line.

1. `VERDICT: PASS`: go to Step 5.

1. `VERDICT: FAIL` and `review_round` is below MAX_REVIEW_ROUNDS: resume the compiler with SendMessage, or dispatch it again with the Step 3 prompt plus `Revision round: fix the findings in <TASK_DIR>/review_<n>.md.` Run lint again as in Step 3, add 1 to `review_round`, and repeat from 1.

1. `VERDICT: FAIL` at MAX_REVIEW_ROUNDS: go to Step 5 and show the remaining `Critical:` findings at the gate.

When a finding is accepted and fixed, add a `- (review) WHEN … → … — WHY …` line under `## Lessons` in state for findings a later compile should avoid, such as a shared file left out of `owns`.

## Step 5: The DAG gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

Build `<TASK_DIR>/gate.md`:

```markdown
# DAG for <task_name>

Source: <source path> (<source_kind>)

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

## Compiler notes
<assumptions and open questions from compile_notes.md, or "none">

## Unresolved review findings
<the Critical findings of the last review if it failed, or "none">

## Cost
<units per skill>. Each build, debug and polish unit runs that skill's full pipeline of agents; rough cost per unit on small units: build about $2.50, debug about $1, polish about $0.50, review about $1, direct about $0.20.
```

**Pre-read**: Read `<TASK_DIR>/gate.md` and capture its full contents.
**State**: `Phase: gate`, `phase_complete: false`, and `awaiting approval: DAG gate` in `what_remains`.

**Surface 1: emit the plan message.** Output the contents verbatim as a chat message:

```text
## Plan for review: orchestrate

<verbatim contents of <TASK_DIR>/gate.md>

---
**Approve** → the units start running  ·  **Reject** → stop, nothing runs  ·  reply with feedback to revise
```

Emit the full contents, never a path, summary or placeholder.

**Surface 2: call AskUserQuestion.** question: "The DAG above is ready for review." header: "DAG gate". Options: **Approve** — fix this DAG and its units · **Reject** — stop without running anything.

**Response handling**:

- **Approve** → add `- DAG approved: <TASK_DIR>/dag.json (<N> units), <UTC date>` under `## Decisions` in state, clear `awaiting approval`, set `phase_complete: true`, and go on to Phase 2 as SKILL.md says.
- **Reject** → set `Status: aborted_by_user` and stop.
- **Any other answer** is feedback. Resume the compiler with the feedback verbatim (or dispatch it again with the Step 3 prompt plus `Revision: apply this feedback from the user: <feedback>`), run lint, run the review loop from round 1, rebuild `gate.md`, and return to Surface 1 with the whole message. When the feedback corrects a mistake rather than a preference, add a `(correction)` line under `## Lessons`. Loop until Approve.
- **No answer** → set `Status: blocked` with `awaiting approval: DAG gate`, and stop. A missing answer is never approval.

**Unattended** (`unattended: true`): emit Surface 1, skip Surface 2, and log the auto-approval as `<PLUGIN_ROOT>/shared/approval-gate.md`, "Unattended mode", says.

**Journal.** After the gate resolves, append the entry that `<PLUGIN_ROOT>/shared/approval-gate.md`, "Journal entry", describes to `<PROJECT_ROOT>/.mz/journal.md`, with `<PLUGIN_ROOT>/shared/journal-artifact.sh <TASK_DIR>/gate.md <PROJECT_ROOT>/.mz/journal.md` for the artifact.
