---
name: brainstorm
description: ALWAYS invoke when the user wants creative ideas, brainstorming, multi-perspective thinking, or diverse viewpoints on a problem. Triggers: "brainstorm", "creative ideas for", "think about this from different angles", "diverse perspectives on".
argument-hint: <topic or problem to brainstorm>
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
---

# Creative Brainstorming Pipeline

## Overview

You orchestrate a multi-personality brainstorming session. A curated panel of 5 thinkers from 10 available personalities generates ideas from diverse lenses, a synthesizer merges them, and the panel votes iteratively until consensus or max rounds.

## When to Use

Invoke when the user wants creative ideation, multi-perspective thinking, or diverse viewpoints on an open problem. Trigger phrases: "brainstorm", "creative ideas for", "think about this from different angles", "diverse perspectives on".

### When NOT to use

- The user wants a single concrete decision or implementation — use `build` or `explain` instead.
- The user wants verification of an existing idea — use `investigate` instead.
- The problem has one objectively correct answer knowable from docs — look it up instead of ideating.

## Input

`$ARGUMENTS` — The topic, problem, or question to brainstorm. If empty, ask the user.

## Constants

- **MAX_ITERATIONS**: 5
- **PANEL_SIZE**: 5
- **TOTAL_PERSONALITIES**: 10
- **MAJORITY_THRESHOLD**: 3
- **TASK_DIR**: `.mz/task/`

## Available Personalities

| Agent                  | Lens                                                  | Best for                                         |
| ---------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| creative-engineer      | Systems thinking, technical feasibility, scalability  | Technical problems, product design, architecture |
| creative-artist        | Aesthetics, form, visual communication, experience    | Design, branding, UX, presentation, media        |
| creative-philosopher   | Meaning, ethics, cultural impact, narrative framing   | Ethics, purpose, messaging, social impact        |
| creative-mathematician | Patterns, optimization, formal logic, structure       | Algorithms, processes, strategy, quantitative    |
| creative-scientist     | Hypotheses, experiments, evidence, natural systems    | Research, validation, methodology, bio-inspired  |
| creative-economist     | Incentives, markets, game theory, resource allocation | Business models, pricing, strategy, growth       |
| creative-storyteller   | Narrative, metaphor, emotional arcs, audience         | Marketing, pitching, content, communication      |
| creative-futurist      | Emerging trends, disruption, long-term trajectories   | Innovation, strategy, roadmaps, future-proofing  |
| creative-psychologist  | Cognition, bias, motivation, behavior, UX             | User research, adoption, persuasion, habits      |
| creative-historian     | Precedent, patterns of change, cultural context       | Risk, lessons learned, positioning, analogies    |

## Core Process

### Phase Overview

| #   | Phase              | Details                       | Loop?            |
| --- | ------------------ | ----------------------------- | ---------------- |
| 0   | Setup              | Inline below                  | --               |
| 1   | Panel Selection    | Inline below                  | --               |
| 1.5 | User Approval      | Inline gate                   | --               |
| 2   | Ideation           | `phases/ideation.md`          | --               |
| 3   | Synthesis + Voting | `phases/voting_and_report.md` | max 5 iterations |
| 4   | Report             | `phases/voting_and_report.md` | --               |

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 23, not discipline. See Rule 17.

## Red Flags

- You collapsed into one-voice output instead of running multiple personas.
- You skipped the critique/voting phase and jumped straight to a report.
- Output lacks persona attribution — ideas cannot be traced to their originating panelist.

## Verification

Before completing, output a visible block showing: selected panel (5 names), iteration count, voting rounds, majority verdict or tie status, and the absolute path of the written report. Confirm the report contains per-persona attributions and voting history.

## Phase 0: Setup

Derive task name as `brainstorm_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) of the topic and HHMMSS is current time. Create `.mz/task/<task_name>/`. Write `state.md` with Status: started, Phase: setup, Started: timestamp, Iteration: 0.

## Phase 1: Panel Selection

Analyze the topic and select the **PANEL_SIZE** (5) best-suited personalities from the table above. Consider:

- What lenses are most relevant to this topic?
- What complementary perspectives would create productive tension?
- Favor diversity of approach over obvious relevance — a historian on a tech problem or an artist on a business problem often produces the most surprising ideas.

Write `.mz/task/<task_name>/panel.md` with the 5 selected agents and a one-sentence justification for each.

Update state phase to `panel_selected`.

## Phase 1.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Present: the topic, the 5 selected panelists with justifications, and the 5 not selected.

Use AskUserQuestion: `Panel assembled for "<topic>". Selected: <list with justifications>. Not selected: <list>. Reply 'approve' to start ideation, 'reject' to abort, or suggest swaps (e.g., "replace economist with historian").`

**Response handling**:

- **"approve"** → update state, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust panel per feedback, update `panel.md`, return to this gate and re-present **via AskUserQuestion** (same format). This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Phase 2: Ideation

Dispatch the 5 selected personality agents in parallel.

**See `phases/ideation.md`** for dispatch prompt template and idea collection.

Update state phase to `ideation_complete`, increment iteration.

## Phase 3: Synthesis + Voting

A randomly-selected panelist synthesizes all ideas, then all 5 vote.

**See `phases/voting_and_report.md` → Phase 3** for synthesis, voting, and convergence check.

If majority reached → proceed to Phase 4. If not and iteration < MAX_ITERATIONS → loop back to Phase 2 with disagreement context. If MAX_ITERATIONS hit → proceed to Phase 4 with best available.

## Phase 4: Report

Compile final report with winning ideas, all perspectives, voting history.

**See `phases/voting_and_report.md` → Phase 4** for report template.

Write to `.mz/reports/brainstorm_<YYYY_MM_DD>_<topic_slug>.md` (append `_v2`, `_v3` if exists). Present summary to user.

## Error Handling

- **Empty topic**: ask via AskUserQuestion. Never guess.
- **Agent returns empty/off-topic**: retry once with clarified prompt. If still empty, exclude from voting and note in report.
- **All iterations exhausted without majority**: report the top 2-3 ideas with vote distribution and all personality feedback. Let the user decide.
- **Tie in votes**: report both tied ideas equally, include all justifications.

## State Management

After each phase, update `.mz/task/<task_name>/state.md`. Track: current phase, iteration count, votes per round, which agents participated. All ideas and votes persist in `.mz/task/<task_name>/history.md` across iterations — this file is passed to agents in subsequent rounds so they build on prior discussion.

Critical: anchor the most important rule at the end — never proceed past the approval gate without explicit user approval. Never skip voting. Never fabricate votes.
