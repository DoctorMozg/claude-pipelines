# Phase 4: Finalization

Full detail for the finalization phase. Covers the user approval gate, the feedback-revision sub-loop, and the final summary artifact.

## Goal

Obtain explicit user approval on the finished design document, apply any final user feedback, and write `final-summary.md` with a comprehensive index and provenance.

## Inputs

From Phase 3:

- `design.md`, `wireframes.md`, `wcag-report.md` — the critique-passed draft
- `critique_<N>.md` — the final synthesis (passed or accepted-with-unresolved)
- The final iteration count
- The aggregate verdict block

## Step 4.1 — User approval gate

**This orchestrator** (not a subagent) must present to the user via `AskUserQuestion`. This step is interactive and must not be delegated.

Use `AskUserQuestion` with this structure:

```
question: "The design document is ready. Approve, reject, or provide feedback?"
header: "Approve doc"
options:
  1. Approve — finalize
     "Write final-summary.md and stop. Files will be left at .mz/design/<task_name>/."
  2. Reject — abort
     "Do not finalize. Mark state as aborted_by_user. Files remain on disk but are marked abandoned."
  3. Provide feedback (use Other)
     "Type changes you want. One more revision round, then re-present. No further critique loop — your word is final."
```

Before the question, emit a presentation block so the user sees what they are approving:

```
Design document is ready at:
  .mz/design/<task_name>/

Iterations used: <N>/5
Aggregate verdict: <PASS|ACCEPTED_WITH_UNRESOLVED>

  ui-designer:              <status>
  ux-designer:              <status>
  art-designer:             <status>
  accessibility-specialist: <status>
  WCAG_GATE:                <status>

Files:
- design.md       (<line count> lines, <section count> sections)
- wireframes.md   (<line count> lines, <diagram count> diagrams)
- wcag-report.md  (<line count> lines, <pair count> pairs)

Key decisions (from design.md §13 Design Rationale):
<first 5 bullets of §13>

Open questions (from design.md §14):
<first 5 bullets of §14>
```

## Step 4.2 — Response handling

- **"approve"** → update state to `complete`, proceed to Step 4.3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not write `final-summary.md`.
- **Feedback (Other)** → apply the feedback, then **return to Step 4.1** with the revised doc. This is a loop — repeat until the user explicitly approves. Never proceed to Step 4.3 without explicit approval.

### Feedback sub-loop

When the user provides feedback instead of approving:

1. Spawn `design-revision-writer` (model: **opus**) with:

```
The user has provided final feedback on the design. Apply it verbatim.

## Task Directory
.mz/design/<task_name>/

## User feedback
<the user's text>

## Read
- .mz/design/<task_name>/design.md
- .mz/design/<task_name>/wireframes.md
- .mz/design/<task_name>/wcag-report.md

## Your Job
Apply the user's feedback. Touch only what the feedback addresses. If the feedback changes colors, regenerate wcag-report.md. Terminal STATUS: line per your agent spec.
```

2. On `DONE` or `DONE_WITH_CONCERNS`, re-present via `AskUserQuestion` (return to Step 4.1).
1. Do **not** re-run the critique loop. The user's word is final after Phase 3.
1. Do **not** accept partial approval. Every round must end in explicit `approve` or `reject`.

## Step 4.3 — Write `final-summary.md`

Only reached after explicit user approval. Write to `.mz/design/<task_name>/final-summary.md`:

```markdown
# Design Document — Final Summary

## Task
<original brief>

## Task ID
<task_name>

## Status
complete | complete_with_unresolved

## Iterations
Used: <N>/5

## Final Verdict
ui-designer:              <status>
ux-designer:              <status>
art-designer:             <status>
accessibility-specialist: <status>
WCAG_GATE:                <status>
AGGREGATE:                <status>

## Artifacts
- .mz/design/<task_name>/design.md
- .mz/design/<task_name>/wireframes.md
- .mz/design/<task_name>/wcag-report.md
- .mz/design/<task_name>/intake.md
- .mz/design/<task_name>/research.md
- .mz/design/<task_name>/critique_1.md ... critique_<N>.md

## Unresolved (if any)
<copy any unresolved Critical findings from the final critique file, or "None">

## Key Decisions
<first 10 bullets of design.md §13 Design Rationale>

## Open Questions
<contents of design.md §14 Open Questions>

## Timeline
- Started:   <timestamp>
- Completed: <timestamp>
```

## Step 4.4 — Update state to complete

```
Status: complete
Phase: 4
PhaseName: finalized
Iteration: <N>
Completed: <timestamp>
FilesWritten:
  - .mz/design/<task_name>/design.md
  - .mz/design/<task_name>/wireframes.md
  - .mz/design/<task_name>/wcag-report.md
  - .mz/design/<task_name>/intake.md
  - .mz/design/<task_name>/research.md
  - .mz/design/<task_name>/critique_1.md
  - ... (critique_2..N)
  - .mz/design/<task_name>/final-summary.md
```

## Step 4.5 — Emit final output

Output a concise completion block visible to the user:

```
Design document finalized.

Task dir: .mz/design/<task_name>/
Iterations: <N>/5
Aggregate: <verdict>

Primary artifact:
  .mz/design/<task_name>/design.md

Read the full summary at:
  .mz/design/<task_name>/final-summary.md
```

Do not print the full design document in the chat — it is on disk, and the user approved its location.

## Notes

- The approval gate here is the user's last line of defense. Never skip it, even if Phase 3 exited cleanly with AGGREGATE PASS. Critic consensus is not user approval.
- The feedback sub-loop is intentional. Users often want a polish pass after seeing the final doc. Support it gracefully — no critique re-run, just a revision.
- `final-summary.md` is the index the user reads first next session. Keep it complete and self-contained — it is the provenance record.
- If the user aborts, leave all files on disk. Do not delete work. The user can resume or discard manually.
