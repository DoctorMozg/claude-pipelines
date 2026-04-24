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

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/design/<task_name>/design.md`, `.mz/design/<task_name>/wireframes.md`, and `.mz/design/<task_name>/wcag-report.md` with the Read tool. Capture the full design document body, ASCII wireframes, and WCAG contrast report into context. The critique loop must have converged with `AGGREGATE: PASS` and zero WCAG violations before this gate fires.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `design.md`, `wireframes.md`, and `wcag-report.md` under labeled sections. Never substitute a path, line count, iteration summary, or `<verdict>` placeholder — the user must review the actual finalized design (including the contrast pairs) in the question itself, not have to open files separately.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Design ready for approval**
All four specialist critics have approved the design, and the WCAG contrast report shows zero violations. Please review the finalized design document, wireframes, and WCAG report below.

- **Approve** → write `final-summary.md` and mark task complete
- **Reject** → mark task aborted and stop
- **Feedback** → dispatch design-revision-writer to apply changes, loop back to this gate
```

Invoke AskUserQuestion with this body (where each `<verbatim ...>` marker is replaced by the bytes you just read):

```
Design document ready (<N>/5 iterations, Aggregate: <verdict>, WCAG: PASS). Please review the finalized design:

## Design Document (design.md)

<verbatim design.md contents>

## Wireframes (wireframes.md)

<verbatim wireframes.md contents>

## WCAG Contrast Report (wcag-report.md)

<verbatim wcag-report.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

## Step 4.2 — Response handling

- **"approve"** → update state to `complete`, proceed to Step 4.3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not write `final-summary.md`.
- **Feedback** → dispatch `design-revision-writer` to apply the feedback, overwrite the affected artifact(s), return to Step 4.1, re-read the updated artifact(s), and re-present **via AskUserQuestion** with the full new contents under each section — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Step 4.3 without explicit approval.

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
