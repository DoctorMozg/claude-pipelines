# Phase 1: Interview — Screen, Ask, Research

Find out what the user actually wants before anything is drafted. A cheap router screen drops exempt changes first; then a short interview settles where the decision stands, which options are in play and what matters most, and researchers aimed at those answers gather the facts the router, the draft and the critics work from. Nothing here writes to `docs/`.

## Inputs (from Phase 0)

- The decision text, the `artifact:` override (or `auto`), the `rich` flag.
- `<PROJECT_ROOT>/.mz/task/<task_name>/provenance.md`, already written, `human_signoff: pending`.
- `state.md` at `Phase: 1`.

## Step 1.1 — Screen: is any artifact needed?

Dispatch `gov-router` on the decision text alone. Single agent, no manifest:

```
Screen this change for governance: run Gate A, and Gate B on what the text says.

## Task Directory
<PROJECT_ROOT>/.mz/task/<task_name>/

## Change to route
<the decision text verbatim>

## Overrides
artifact: <adr | rfd | design | auto>
rich: <true | false>

## Algorithm
Read <SKILL_DIR>/references/artifact-router.md and apply Gate A then Gate B verbatim. There is no brief yet: this is the screen, and Phase 2 routes again once the user has answered.

## Output
Write the routing decision to <PROJECT_ROOT>/.mz/task/<task_name>/routing.md and emit the decision block (ARTIFACT / GATE_FIRED / WEIGHT / STATUS_VOCAB / OVERRIDE + rationale), then STATUS:.
```

Handle its `STATUS:` line:

- `DONE` / `DONE_WITH_CONCERNS` → go on (log a concern to `state.md`).
- `NEEDS_CONTEXT` → the decision text is too thin even to screen. Ask the router's named gap with AskUserQuestion, then dispatch again with the answer appended to the change text.
- `BLOCKED` → `artifact-router.md` is unreadable or no change was supplied. Escalate via AskUserQuestion; never invent a routing.

Emit a visible block: `ARTIFACT`, `WEIGHT` and the one-line rationale, marked `screen`.

### Exemption path (`ARTIFACT: none`)

Gate A found the change not substantial-and-ambiguous. Do **not** interview, research, draft, discuss or gate:

1. Append a one-line exemption note to `state.md` under `## Exemption`: the router's reason verbatim (e.g. "behavior-preserving refactor — exempt under Gate A").
1. Keep `provenance.md` as the run record: the exemption is itself a governed outcome worth tracing.
1. Update `state.md`: `Status: complete`, `Phase: 1`, `phase_complete: true`, `what_remains: []`. Append `routing.md` to `FilesWritten`, so the exempt run records both it and `provenance.md`.
1. Report to the user that the decision needs no governance artifact, with the one-line reason and the path to `routing.md`. **Stop the pipeline here.**

Routing `none` is a real result, not a failure: the cheap, correct outcome for routine work.

Any other `ARTIFACT` is provisional. Record it in `state.md` as `ScreenArtifact` and go on.

## Step 1.2 — Read before asking

Read enough to ask good questions, and never ask what these answer:

- `CLAUDE.md` and the README at `PROJECT_ROOT`: the project's purpose and stated constraints.
- The existing records: Glob `docs/decisions/*.md`, `docs/rfcs/*.md` and `docs/design/*.md`, and Grep each for its title and `status`. Note any record on the same subject as this decision.
- The code: Grep for the components, libraries and modules the decision names, to see what exists today and which options are real.

## Step 1.3 — Ask

List what the draft needs and the decision text leaves open, then ask it in **one** AskUserQuestion call of at most **MAX_QUESTIONS** questions. This is an input collector, not a gate: no plan message before it, no Approve or Reject. Each question offers two to four concrete options from the code and the decision, the most likely first; the user types anything else.

| Header       | Ask when                                                      | Options                                                                                                                                                                                                                                                                                                   |
| ------------ | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Stage`      | No `artifact:` override, and the text doesn't settle it       | **Help me choose**: the panel weighs the options and you sign off on one, recorded as an ADR · **Already decided**: record the choice and why, an ADR · **Team debates first**: publish it for discussion with the outcome open, an RFD · **Decided, need a build spec**: how it gets built, a design doc |
| `Options`    | The text names fewer than two options, or Step 1.2 found more | The options named, plus real alternatives the code or the domain suggests; `multiSelect: true`                                                                                                                                                                                                            |
| `Priorities` | Always, unless the text states the criteria                   | Two to four criteria that fit this decision, such as latency, cost, operational burden, reversibility or team familiarity; `multiSelect: true`                                                                                                                                                            |
| `Related`    | Step 1.2 found a record on the same subject                   | **Supersedes `<record>`** · **Extends it, keep both** · **Unrelated**                                                                                                                                                                                                                                     |

Nothing open: skip the call and say in one line that the decision text settles stage, options and priorities.

**Unattended**, or no AskUserQuestion in your tool list, or the call is denied: skip it and put every open point under `## Assumptions` with the most likely answer. Phase 4 still needs a person, so such a run stops there; the assumptions let research and the draft go ahead.

## Step 1.4 — Write the brief

Write `<PROJECT_ROOT>/.mz/task/<task_name>/brief.md`: the decision text verbatim, then `## Answers` with each question and its answer (and `Stage: choose | decided | debate | build`), `## Related records` with paths and statuses, and `## Assumptions` for anything still open. Append it to `FilesWritten`.

## Step 1.5 — Research what the brief points at

Agents can't see this conversation, so they get the brief's path. Dispatch, in **one** message:

- One `pipeline-researcher` for the code, always, even when you have read it yourself: its report is what the router, the draft and the critics check against.
- One `pipeline-web-researcher` per piece of outside technology the decision depends on (a library, a service, a protocol, a hosted product), whether it is an option itself or something every option must handle, such as a provider's API, and only when its behavior, cost or limits bear on the brief's priorities; at most **MAX_WEB_RESEARCHERS**. A decision that involves only this codebase needs none. With no web tools in the session, skip these dispatches and note under `## Gaps` what stays unconfirmed.

Emit the manifest first:

```
Dispatching governance research — <N> agents in parallel
Purpose: facts behind the options in brief.md
- pipeline-researcher — code the decision touches
- pipeline-web-researcher — <technology, ≤6 words>
```

`pipeline-researcher` gets:

```
Research the code behind a design decision that is about to be made.

Decision and the user's answers: <PROJECT_ROOT>/.mz/task/<task_name>/brief.md
Repository: <PROJECT_ROOT>

Report: where the decision lands today, with the files, modules and config involved; the callers and consumers each option would affect; constraints the code already sets (versions, interfaces, data formats, tests that pin behavior); and earlier decisions visible in code or docs. Name paths. Cover only what the brief's options and priorities make relevant.
```

Each `pipeline-web-researcher` gets:

```
Research one piece of outside technology a design decision depends on, against primary sources.

Decision and the user's answers: <PROJECT_ROOT>/.mz/task/<task_name>/brief.md
Technology: <the library, service or product>
Questions: <the brief's priorities, asked about it, e.g. "p99 read latency at our scale", "what running it in production takes">

Report sourced facts with a confidence level for each, and mark what you could not confirm.
```

The researchers return text. When every one has returned, emit the rollup:

```
Wave complete (research) — <returned>/<dispatched> agents returned
- pipeline-researcher: <STATUS> — code
- pipeline-web-researcher: <STATUS> — <technology>
```

Write `<PROJECT_ROOT>/.mz/task/<task_name>/research.md` with one section per researcher, `## Code` then `## <technology>`, each report verbatim. A researcher that returns nothing usable is dispatched once more; if it fails again, add a `## Gaps` line naming what is missing, a `- (failure) WHEN … → … — WHY …` line under `## Lessons` in `state.md`, and go on. Never fill a gap from memory. Append `research.md` to `FilesWritten`.

### Questions the research raises

Research often turns up a question only the user can settle, one that changes the draft's shape: a constraint the code contradicts, a provider behavior that rules an option in or out. Ask those in **one** more AskUserQuestion call of at most **MAX_QUESTIONS**, with the same rules as Step 1.3, and add the answers to `brief.md` under `## Answers`. Questions that only refine a detail go into the draft as `<to be resolved in discussion>` instead, for the critics and the gate. Unattended, or with no AskUserQuestion: record each one under `## Assumptions` with your default and go on.

Never ask in prose and stop: an answer typed into chat after the run ends never reaches `brief.md`, and the pipeline stalls before the draft.

## Step 1.6 — Advance

Update `state.md`: `Phase: 2`, `phase_complete: true` for Phase 1, `what_remains` (e.g. "route with the brief", "draft", "discuss panel", "human sign-off gate", "write to docs/"). Emit a short block with the stage, the options and the research sections written, then read `phases/propose.md`.
