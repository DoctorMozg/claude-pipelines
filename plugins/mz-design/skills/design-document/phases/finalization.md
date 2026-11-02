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

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/design/<task_name>/design.md`, `<PROJECT_ROOT>/.mz/design/<task_name>/wireframes.md`, and `<PROJECT_ROOT>/.mz/design/<task_name>/wcag-report.md` with the Read tool. Capture the full design document body, ASCII wireframes, and WCAG contrast report into context. Read `LastVerdict` and `unresolved` from `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`: Phase 3 ends with `AGGREGATE: PASS`, or with the user accepting unresolved findings at the iteration cap.

**State**: write `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` with `Phase: 4`, `PhaseName: approval`, `phase_complete: false` and `what_remains: [awaiting approval: design gate]`. `Status` stays `running`.

**Surface 1 — emit the plan message.** Output the three artifacts verbatim as a normal markdown chat message. Emit the full verbatim contents — never substitute a path, line count, iteration summary, or `<verdict>` placeholder; the user reviews the actual finalized design (including the contrast pairs) in the message itself. Structure:

```
## Plan for review: design-document

Design document finalized (<N>/5 iterations · Aggregate: <verdict> · WCAG: <PASS or FAIL>). <"All four specialist critics passed the design." or "Unresolved findings accepted at the iteration cap: <count>, listed in critique_<N>.md.">

### Design Document (design.md)

<verbatim design.md contents>

### Wireframes (wireframes.md)

<verbatim wireframes.md contents>

### WCAG Contrast Report (wcag-report.md)

<verbatim wcag-report.md contents>

---
**Approve** → write `final-summary.md` and finish the task  ·  **Reject** → mark the task aborted, nothing more written  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the design artifacts in the question body, they live in the plan message above:

- question: `The finalized design above is ready for review.`
- header: `Design`
- options: **Approve** — write `final-summary.md` and complete the task · **Reject** — abort the task, write nothing further

## Step 4.2 — Response handling

- **Approve** → add `- design approved: .mz/design/<task_name>/design.md, wireframes.md, wcag-report.md` under `## Decisions` in `state.md`, remove the `awaiting approval` entry, and go to Step 4.3. `Status` stays `running` until Step 4.4.
- **Reject** → update state to `aborted_by_user` and stop. Do not write `final-summary.md`.
- **Any other reply (feedback)** → dispatch `design-revision-writer` to apply the feedback, overwrite the affected artifact(s), return to Step 4.1, re-read the updated artifact(s), and re-emit the entire plan message from scratch with the full new contents under each section — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Step 4.3 without explicit approval. Typed text, a "Chat about this" reply, and an Approve whose note asks for a change all count as feedback.
- **No answer** (AskUserQuestion denied or unavailable, or the result carries the away signal) → set `Status: blocked`, keep `awaiting approval: design gate` in `what_remains`, and stop. A missing answer is never approval.

After the gate resolves, append a gate entry to `<PROJECT_ROOT>/.mz/journal.md` with the artifact recipe in `<PLUGIN_ROOT>/shared/approval-gate.md`, "Journal entry".

## Step 4.3 — Write `final-summary.md`

Only reached after explicit user approval. Write to `<PROJECT_ROOT>/.mz/design/<task_name>/final-summary.md`:

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
schema_version: 2
Status: complete
Phase: 4
PhaseName: finalized
Started: <timestamp from setup>
Iteration: <N>
FilesWritten:
  - .mz/design/<task_name>/design.md
  - .mz/design/<task_name>/wireframes.md
  - .mz/design/<task_name>/wcag-report.md
  - .mz/design/<task_name>/intake.md
  - .mz/design/<task_name>/research.md
  - .mz/design/<task_name>/critique_1.md
  - ... (critique_2..N)
  - .mz/design/<task_name>/final-summary.md
phase_complete: true
what_remains: []
Completed: <timestamp>
LastVerdict: <keep the Phase 3 block>
unresolved: <count>
```

## Step 4.5 — Emit final output

Output a concise completion block visible to the user:

```
Design document finalized.

Task dir: <PROJECT_ROOT>/.mz/design/<task_name>/
Iterations: <N>/5
Aggregate: <verdict>

Primary artifact:
  <PROJECT_ROOT>/.mz/design/<task_name>/design.md

Read the full summary at:
  <PROJECT_ROOT>/.mz/design/<task_name>/final-summary.md
```

Do not print the full design document in the chat — it is on disk, and the user approved its location.

## Notes

- The approval gate here is the user's last line of defense. Never skip it, even if Phase 3 exited cleanly with AGGREGATE PASS. Critic consensus is not user approval.
- The feedback sub-loop is intentional. Users often want a polish pass after seeing the final doc. Support it gracefully — no critique re-run, just a revision.
- `final-summary.md` is the index the user reads first next session. Keep it complete and self-contained — it is the provenance record.
- If the user aborts, leave all files on disk. Do not delete work. The user can resume or discard manually.
