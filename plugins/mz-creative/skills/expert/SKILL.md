---
name: expert
description: ALWAYS invoke when the user wants a multi-sided expert critique of an idea. Triggers:"expert review of","consult experts on","critique this idea","multi-angle analysis","strengths and weaknesses of". Provide the idea as the argument.
argument-hint: <idea or proposal to review>
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
model: sonnet
---

# Expert Consultation Pipeline

## Overview

You orchestrate a Delphi-style expert panel review. A curated panel of 5 lenses — selected from 16 available perspectives — critiques an idea over **3 fixed rounds**. Each round every panelist emits a structured 5-field view (strengths/weaknesses/risks/suggestions/confidence); a neutral round synthesizer consolidates the outputs; the next round's panelists receive the summary plus their own prior view and may alter their position. After round 3, a dedicated report writer produces a multi-sided analysis report.

## When to Use

Invoke when the user wants a critical, multi-lens analysis of a specific proposal, plan, architecture, business idea, or design decision. Trigger phrases: "expert review of", "critique this idea", "strengths and weaknesses of", "multi-angle analysis", "consult experts on".

### When NOT to use

- The user wants to generate ideas from scratch — use `brainstorm`.
- The user wants a single concrete decision or implementation — use `build`.
- The user wants verification of an existing codebase change — use `audit` or `review-branch`.
- The problem has one objectively correct answer knowable from docs — look it up instead of consulting a panel.

## Input

`$ARGUMENTS` — The idea, proposal, or plan to review. Supports inline modifiers:

- `scope:branch|global|working` — when set, `expert-researcher` scans the codebase first so experts can ground feedback in real code (default: pure idea analysis, no scan)
- `@doc:<path>` — existing requirement/brief/RFC document to ingest

If `$ARGUMENTS` is empty, ask the user via `AskUserQuestion`. Never guess.

## Constants

- **PANEL_SIZE**: 5
- **TOTAL_LENSES**: 16
- **ROUNDS**: 3 (fixed — no early stopping, no convergence check)
- **TASK_DIR**: `.mz/task/`
- **REPORT_DIR**: `.mz/reports/`

## Available Lenses

Panel picks 5 from 16 lenses: `lens-engineer`, `lens-artist`, `lens-philosopher`, `lens-mathematician`, `lens-scientist`, `lens-economist`, `lens-storyteller`, `lens-futurist`, `lens-psychologist`, `lens-historian`, `lens-cto`, `lens-seo`, `lens-security`, `lens-product`, `lens-devops`, `lens-data`.
Use the brief to balance primary, adjacent, and productive-tension lenses. Behavior is injected by this skill (critique mode); the same lens agents serve `/brainstorm` in ideation mode.

## Core Process

### Phase Overview

| #   | Phase                              | File                                                      | Loop?                        |
| --- | ---------------------------------- | --------------------------------------------------------- | ---------------------------- |
| 0   | Setup                              | inline below                                              | —                            |
| 1   | Intake + Optional Research + Panel | `phases/intake_and_panel.md`                              | —                            |
| 1.5 | Panel Approval Gate                | Inline below (+ `phases/intake_and_panel.md` for details) | user-feedback sub-loop       |
| 2   | Round Loop                         | `phases/round_loop.md`                                    | fixed 3 rounds, no early-out |
| 3   | Final Report                       | `phases/final_report.md`                                  | —                            |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. Extract brief, `scope:`, `@doc:` refs.
1. If brief is empty → `AskUserQuestion`. Never guess.
1. `task_name` = `<YYYY_MM_DD>_expert_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and slug is a snake_case summary (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status`, `Phase`, `Started`, `Round: 0`, `FilesWritten: []`.
1. Emit a visible setup block: `task_name`, working dir, report dir, detected modifiers.

### Phase 1.5: Panel Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/panel.md` with the Read tool. Capture the full file contents (5 selected panelist lenses with one-line rationale per pick — primary, adjacent, productive-tension picks all justified) into context. See `phases/intake_and_panel.md` Step 1.4 for the panel.md content schema.

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `panel.md`. Never substitute a path, status summary, or `<5 lens names>` placeholder — the user must review the actual panel composition and rationale in the question itself, not have to open the file separately. The user confirms the panel composition before any of the 3 rounds dispatch.

Invoke AskUserQuestion with this body (where `<verbatim panel.md contents>` is replaced by the bytes you just read):

```
Panel assembled. Please review the composition before the 3 rounds begin:

<verbatim panel.md contents>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

Before invoking AskUserQuestion, emit a text block to the user:

```
**Panel ready for approval**
5 expert lenses selected to critique your idea over 3 rounds. Review the composition below and confirm you want to proceed.

- **Approve** → begin 3 rounds of expert critique
- **Reject** → cancel task, no rounds will run
- **Feedback** → request changes to panel composition, iterate until approved
```

**Response handling**:

- **"approve"** → update `state.md` to `panel_approved`, proceed to Phase 2 (Round Loop).
- **"reject"** → update `state.md` to `aborted_by_user` and stop. Do not run rounds.
- **Feedback** → apply swaps/changes, overwrite `panel.md`, return to this gate, re-read `panel.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill, not a discipline skill.

## Red Flags

- You skipped the panel-approval gate.
- You exited the round loop before 3 rounds completed.
- You serialized the 5 panelists instead of dispatching in one parallel message per round.
- You let a panelist write `round_<N>_summary.md` instead of dispatching `expert-round-synthesizer`.
- You wrote the final report inline instead of dispatching `expert-report-writer`.
- The final report has claims not attributed to a specific panelist + round.

## Verification

At the end of Phase 3, output a visible block:

```
Expert consultation finalized.
Task dir:   .mz/task/<task_name>/
Report:     .mz/reports/<YYYY_MM_DD>_expert_<slug>.md
Panel:      <5 agent names>
Rounds:     3/3
Files:
  - intake.md
  - research.md (if scope: set)
  - panel.md
  - iter_1_<agent>.md × 5, round_1_summary.md
  - iter_2_<agent>.md × 5, round_2_summary.md
  - iter_3_<agent>.md × 5, round_3_summary.md
  - final report at .mz/reports/
```

If any phase is incomplete, print the blocker explicitly. The verification block is mandatory.

## Error Handling

- Empty brief → `AskUserQuestion`; never guess.
- `@doc:` path does not exist → ask the user whether to proceed without it.
- Agent returns malformed output → retry once with clarified prompt; if still malformed, note the gap in state.md and continue (do not block the round on a single agent).
- Researcher fails when `scope:` set → escalate to user; offer to proceed without scan.
- Panel-approval gate rejected → mark state `aborted_by_user`; stop without writing a report.
- Update `state.md` before and after every agent dispatch.

## State Management

After each phase, update `.mz/task/<task_name>/state.md`:

- `Status:` `pending` | `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` `0` | `1` | `1.5` | `2` | `3`
- `Round:` `0..3` (Phase 2 only)
- `FilesWritten:` cumulative list

Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions. The state file is the source of truth.
