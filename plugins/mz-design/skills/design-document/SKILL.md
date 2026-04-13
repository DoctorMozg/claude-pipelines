---
name: design-document
description: ALWAYS invoke when the user wants a UI/UX design document or interface spec. Triggers:"design a UI for X","create a design document","design spec","UX spec". Provide a brief as the argument.
model: sonnet
allowed-tools: Agent(design-researcher), Agent(design-document-writer), Agent(ui-designer), Agent(ux-designer), Agent(art-designer), Agent(accessibility-specialist), Agent(design-critique-synthesizer), Agent(design-revision-writer), AskUserQuestion, Read, Write, Grep, Bash, WebSearch
---

# Design Document Pipeline

## Overview

Takes a UI/UX design brief and produces a comprehensive design document with ASCII wireframes, Mermaid diagrams, and a WCAG 2.2 AA contrast report. Refines the draft through four specialist critics in parallel (ui-designer, ux-designer, art-designer, accessibility-specialist) with a WCAG hard gate, for up to 5 iterations, until all critics approve and zero contrast violations remain.

## When to Use

- User asks to create a UI/UX design document, interface specification, or UX spec.
- Triggers: "design a X page/screen/flow", "create a design document for X", "design spec for X", "UX spec for X".
- Work produces a spec document (not implementation) for software UI/UX.

### When NOT to use

- Implementing the design in code — use `build` (mz-dev-pipe).
- Reviewing an existing design doc — use `audit` or `review-branch`.
- Brainstorming directions without committing to a spec — use `brainstorm` (mz-creative).
- Print, brand, or industrial design — out of scope for this skill.

## Input

`$ARGUMENTS` — The design brief. Supports inline modifiers:

- `scope:branch|global|working` — codebase scope for design-researcher (default: `global`)
- `@image:<path>` — reference image path (acknowledged, not decoded)
- `@doc:<path>` — existing requirement/brief document to ingest

If empty, ask the user for a brief via `AskUserQuestion`. Never guess.

## Constants

- **MAX_DESIGN_ITERATIONS**: 5
- **DESIGN_DIR**: `.mz/design/`
- **TASK_NAME_FORMAT**: `design_<slug>_<HHMMSS>`
- **WCAG_AA_NORMAL**: 4.5
- **WCAG_AA_LARGE**: 3.0

## Core Process

### Phase Overview

| #   | Phase             | File                                                       | Loop?                           |
| --- | ----------------- | ---------------------------------------------------------- | ------------------------------- |
| 0   | Setup             | inline below                                               | —                               |
| 1   | Intake & Research | `phases/intake_and_research.md`                            | —                               |
| 2   | Initial Draft     | `phases/initial_draft.md`                                  | —                               |
| 3   | Critique Loop     | `phases/critique_loop.md`                                  | max `MAX_DESIGN_ITERATIONS` (5) |
| 4   | Finalization      | Inline gate below (+ `phases/finalization.md` for details) | user-approval sub-loop          |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. Extract brief, `scope:`, `@image:` refs, `@doc:` refs.
1. If brief is empty → `AskUserQuestion` asking for the brief. Do not guess.
1. Derive task name as `design_<slug>_<HHMMSS>` where slug is a snake_case summary of the brief (max 20 chars) and HHMMSS is wall-clock time.
1. Create `.mz/design/<task_name>/`.
1. Write `state.md` with `Status`, `Phase`, `Started`, `Iteration: 0`, `FilesWritten: []`.
1. Output a visible setup block showing: `task_name`, `DESIGN_DIR` path, detected modifiers.

### Phase 4: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: the finalized design document draft (path + summary of iterations, aggregate verdict, WCAG gate result) after the critique loop has converged with `AGGREGATE: PASS` and zero WCAG violations. See `phases/finalization.md` Step 4.1 for extended presentation details and the revision-writer sub-loop.

Use AskUserQuestion with:

```
Design document ready at .mz/design/<task_name>/design.md (<N>/5 iterations, Aggregate: <verdict>, WCAG: PASS).

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update `state.md` to `complete`, proceed to write `final-summary.md`.
- **"reject"** → update `state.md` to `aborted_by_user` and stop. Do not write `final-summary.md`.
- **Feedback** → dispatch `design-revision-writer` to apply the feedback, return to this gate, re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves. Never proceed to `final-summary.md` without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                      | Rebuttal                                                                                                                                                                    |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The first draft is fine, skip the critique loop"    | "Four parallel critics catch issues in one round that would surface as rework during implementation. The loop costs 5 agents per round and prevents 10+ downstream cycles." |
| "WCAG AA is overkill for internal tools"             | "Internal users include colleagues with visual impairments. AA is the legal floor, not a stretch goal. The hard gate is non-negotiable."                                    |
| "Mermaid diagrams and ASCII wireframes are busywork" | "Flow diagrams surface IA gaps invisible in prose. Wireframes make layout decisions concrete — without them, ui-designer has nothing to critique."                          |
| "I'll approve iteration 1 to save time"              | "The 5-iteration cap is a ceiling, not a target. Most drafts pass in 1–2 rounds. Approving an unreviewed draft defeats the purpose of the specialist critics."              |

## Red Flags

- You dispatched the writer before the researcher returned `STATUS: DONE`.
- You accepted `AGGREGATE: FAIL` and advanced without running the revision writer.
- You advanced past `MAX_DESIGN_ITERATIONS` without escalating to the user.
- You trusted the writer's self-reported WCAG numbers instead of the accessibility-specialist's re-validation.
- You presented the final doc without the Phase 4 user approval gate.
- You serialized the four critics instead of dispatching them in parallel (single message, four Agent calls).

## Verification

At the end of Phase 4, output:

```
Design document finalized.
Task dir:   .mz/design/<task_name>/
Iterations: <N>/5
Aggregate:  <PASS | ACCEPTED_WITH_UNRESOLVED>
WCAG gate:  <PASS | FAIL>
Files:
  - design.md (<lines>)
  - wireframes.md (<lines>)
  - wcag-report.md (<lines> — <pair count> pairs)
  - final-summary.md
```

If any phase is incomplete, print the blocker explicitly. The verification block is mandatory — do not skip it.

## Error Handling

- Agent failure → retry once, then escalate via `AskUserQuestion`.
- Brief is empty → ask the user; never guess.
- `@image:` path does not exist → note in `intake.md`, continue with placeholder.
- `@doc:` path does not exist → ask the user whether to proceed without it.
- WCAG hard gate fails at iteration 5 → escalate with options (accept as-is, provide guidance for one more round, abort).
- Critic emits malformed output → treat as FAIL, proceed to revision.
- Always update `state.md` before and after spawning agents.

## State Management

After each phase, update `.mz/design/<task_name>/state.md` with:

- `Status:` `pending` | `running` | `complete` | `complete_with_unresolved` | `aborted_by_user` | `failed`
- `Phase:` `0` | `1` | `2` | `3` | `4`
- `PhaseName:` short label (`setup`, `intake_and_research_complete`, etc.)
- `Iteration:` `0..MAX_DESIGN_ITERATIONS`
- `LastVerdict:` (Phase 3 only) the 6-line verdict block from `critique_<N>.md`
- `FilesWritten:` cumulative list of paths

Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions. The state file is the source of truth.
