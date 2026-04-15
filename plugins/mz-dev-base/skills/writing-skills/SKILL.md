---
name: writing-skills
description: ALWAYS invoke when the user asks to "write a skill", "author a new skill", "create a SKILL.md", or "add a skill to the plugin". Enforces SKILL_GUIDELINES.md via a TDD-style authoring workflow.
argument-hint: <skill name or intent>
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion
model: sonnet
---

# Writing Skills

Meta-skill for authoring new skills in this repository. Applies SKILL_GUIDELINES.md through a TDD-style authoring loop: RED (enumerate rationalizations the skill will face), GREEN (write the counter-arguments into the canonical 7-section anatomy), REFACTOR (re-read as a skeptic and stress-test the description, triggers, and rationalization table).

## Overview

This skill turns SKILL_GUIDELINES.md from a passive rulebook into an executable authoring workflow. Every new skill the user asks to create is walked through the same three-step loop. RED finds the excuses a future invocation will raise to skip the skill. GREEN writes the canonical body whose rationalization table directly rebuts those excuses. REFACTOR subjects the draft to a skeptical re-read and the pre-publish checklist before the user approves.

## When to Use

Triggers: "write a skill", "author a new skill", "create a SKILL.md", "add a skill to the plugin", "turn this rule into a skill", "help me make this skill follow guidelines".

### When NOT to use

- Auditing or fixing an already-merged skill's CSO/anatomy compliance — use `review-branch` or `review-pr` instead.
- Editing phase files inside an existing skill without changing its SKILL.md or references — just edit directly.
- Writing non-skill markdown (rules, agent files, plan docs) — this skill is scoped to `plugins/<plugin>/skills/<name>/SKILL.md` authoring only.

## Core Process

| Phase | Goal                                   | Details               |
| ----- | -------------------------------------- | --------------------- |
| 0     | Setup                                  | Inline below          |
| 1     | TDD authoring (RED / GREEN / REFACTOR) | `phases/authoring.md` |

### Phase 0: Setup

1. **Parse arguments**: `$ARGUMENTS` is the skill name or a short intent string. If empty, ask the user what skill to author and which plugin it belongs in.
1. **Scope**: identify the target plugin directory under `plugins/` (e.g. `mz-dev-base`, `mz-dev-pipe`). Confirm with the user if ambiguous.
1. **Classify skill type** per SKILL_GUIDELINES.md: discipline (pushes back against shortcuts), collaboration (shared output with the user), or reference (neutral knowledge). The classification determines the persuasion register the skill must use and whether an anti-rationalization table is required.

Proceed to Phase 1 by reading `phases/authoring.md`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration skill, not discipline.

## Red Flags

- You wrote a draft SKILL.md without filling in the Common Rationalizations or Red Flags sections. The anatomy is incomplete — return to RED and enumerate excuses before shipping.
- The description reads like a workflow summary ("Orchestrates X, then Y, then Z") instead of a CSO trigger list. Descriptions are the skill's auction bid for invocation, not a table of contents.
- You skipped the persuasion-register check. Discipline skills must use Authority/Commitment/Social-Proof framing; Liking language is banned for them because it drops compliance from 72% to 33% per Meincke et al. (2025).

## Verification

Run the pre-publish checklist at the end of Phase 1. Every bullet must be green before the skill is considered done:

- Description is CSO-compliant, ≤250 chars, triggers only, no workflow tail.
- SKILL.md ≤150 lines; phase files ≤400 lines.
- All 7 canonical sections present, in order.
- Anti-rationalization table present with ≥3 rows if discipline skill.
- Persuasion register matches skill type; no Liking language in discipline skills.
- All `phases/*.md` and `references/*.md` pointers resolve.
- User has explicitly approved the final draft via the Phase 1 approval gate.

Output the checklist result as a visible block before concluding — silent checks get skipped.

## References

- Reference: grep `references/persuasion-principles.md` for Cialdini principle applications per skill type.
- Reference: grep `references/anti-rationalization-library.md` for seed rationalization/rebuttal pairs.
- Reference: grep `references/canonical-skill-anatomy.md` for the 7-section skeleton template.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- `Status:` `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` current phase number
- `SkillType:` classified skill type from Phase 0
- `DraftPath:` path to the in-progress SKILL.md or phase file

Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.
