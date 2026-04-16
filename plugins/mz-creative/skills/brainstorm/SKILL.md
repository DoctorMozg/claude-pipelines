---
name: brainstorm
description: ALWAYS invoke when the user wants creative ideas, brainstorming, multi-perspective thinking, or diverse viewpoints on a problem. Triggers: "brainstorm", "creative ideas for", "think about this from different angles", "diverse perspectives on".
argument-hint: <topic or problem to brainstorm>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, WebFetch, WebSearch
---

# Creative Brainstorming Pipeline

## Overview

You orchestrate a multi-lens brainstorming session. A curated panel of 5 thinkers from 16 available lenses generates ideas from diverse perspectives, a synthesizer merges them, and the panel votes iteratively until consensus or max rounds.

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
- **TOTAL_LENSES**: 16
- **MAJORITY_THRESHOLD**: 3
- **TASK_DIR**: `.mz/task/`

## Available Lenses

| Agent              | Lens                                                  | Best for                                                 |
| ------------------ | ----------------------------------------------------- | -------------------------------------------------------- |
| lens-engineer      | Systems thinking, technical feasibility, scalability  | Technical problems, product design, architecture         |
| lens-artist        | Aesthetics, form, visual communication, experience    | Design, branding, UX, presentation, media                |
| lens-philosopher   | Meaning, ethics, cultural impact, narrative framing   | Ethics, purpose, messaging, social impact                |
| lens-mathematician | Patterns, optimization, formal logic, structure       | Algorithms, processes, strategy, quantitative            |
| lens-scientist     | Hypotheses, experiments, evidence, natural systems    | Research, validation, methodology, bio-inspired          |
| lens-economist     | Incentives, markets, game theory, resource allocation | Business models, pricing, strategy, growth               |
| lens-storyteller   | Narrative, metaphor, emotional arcs, audience         | Marketing, pitching, content, communication              |
| lens-futurist      | Emerging trends, disruption, long-term trajectories   | Innovation, strategy, roadmaps, future-proofing          |
| lens-psychologist  | Cognition, bias, motivation, behavior, UX             | User research, adoption, persuasion, habits              |
| lens-historian     | Precedent, patterns of change, cultural context       | Risk, lessons learned, positioning, analogies            |
| lens-cto           | Architecture, build-vs-buy, tech-debt, org impact     | Technology strategy, platform leverage, delivery risk    |
| lens-data          | Measurement, experimentation, instrumentation, growth | Metrics design, A/B tests, analytics, growth loops       |
| lens-devops        | Reliability, SLOs, observability, capacity, cost      | Production systems, on-call, rollout, operational burden |
| lens-product       | PMF, jobs-to-be-done, prioritization, kill criteria   | Roadmap, MVP scoping, user value, backlog tradeoffs      |
| lens-security      | Threat modeling, attack surface, authZ, compliance    | Appsec review, data handling, trust boundaries           |
| lens-seo           | Search intent, content strategy, technical SEO        | Organic growth, content planning, indexing decisions     |

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

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You collapsed into one-voice output instead of running multiple personas.
- You skipped the critique/voting phase and jumped straight to a report.
- Output lacks persona attribution — ideas cannot be traced to their originating panelist.

## Verification

Before completing, output a visible block showing: selected panel (5 names), iteration count, voting rounds, majority verdict or tie status, and the absolute path of the written report. Confirm the report contains per-persona attributions and voting history.

## Phase 0: Setup

Derive task name as `brainstorm_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) of the topic and HHMMSS is current time. Create `.mz/task/<task_name>/`. Write `state.md` with Status: started, Phase: setup, Started: timestamp, Iteration: 0.

## Phase 1: Panel Selection

Analyze the topic and select the **PANEL_SIZE** (5) best-suited lenses from the table above. Consider:

- What lenses are most relevant to this topic?
- What complementary perspectives would create productive tension?
- Favor diversity of approach over obvious relevance — a historian on a tech problem or an artist on a business problem often produces the most surprising ideas.

Write `.mz/task/<task_name>/panel.md` with the 5 selected agents and a one-sentence justification for each.

Update state phase to `panel_selected`.

## Phase 1.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Mandatory pre-read**: Read `.mz/task/<task_name>/panel.md` with the Read tool. Capture the full file contents (5 selected panelist agents with one-sentence justifications) into context. Also list the 5 not-selected lenses inline (derive from the 16-lens table minus the 5 in `panel.md`).

**Mandatory inline-verbatim presentation**: The AskUserQuestion question body must contain the verbatim contents of `panel.md` plus the inline list of not-selected lenses. Never substitute a path, status summary, or `<list with justifications>` placeholder — the user must review the actual panel composition in the question itself, not have to open the file separately.

Invoke AskUserQuestion with this body (where `<verbatim panel.md contents>` is replaced by the bytes you just read):

```
Panel assembled for "<topic>".

Selected (with justifications):
<verbatim panel.md contents>

Not selected: <comma-separated list of 11 remaining lens names>

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

**Response handling**:

- **"approve"** → update state, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust panel per feedback, overwrite `panel.md`, return to this gate, re-read `panel.md`, and re-present **via AskUserQuestion** with the full new contents — never diff-only, never summary-only, since context compaction may have destroyed the user's memory of earlier iterations. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Phase 2: Ideation

Dispatch the 5 selected personality agents in parallel. **See `phases/ideation.md`** for dispatch prompt template and idea collection. Update state phase to `ideation_complete`, increment iteration.

## Phase 3: Synthesis + Voting

A randomly-selected panelist synthesizes all ideas, then all 5 vote.

**See `phases/voting_and_report.md` → Phase 3** for synthesis, voting, and convergence check.

If majority reached → proceed to Phase 4. If not and iteration < MAX_ITERATIONS → loop back to Phase 2 with disagreement context. If MAX_ITERATIONS hit → proceed to Phase 4 with best available.

## Phase 4: Report

Compile final report with winning ideas, all perspectives, and voting history. **See `phases/voting_and_report.md` → Phase 4** for report template. Write to `.mz/reports/brainstorm_<YYYY_MM_DD>_<topic_slug>.md` (append `_v2`, `_v3` if exists). Present summary to user.

## Error Handling

- **Empty topic**: ask via AskUserQuestion. Never guess.
- **Agent returns empty/off-topic**: retry once with clarified prompt. If still empty, exclude from voting and note in report.
- **All iterations exhausted without majority**: report the top 2-3 ideas with vote distribution and all personality feedback. Let the user decide.
- **Tie in votes**: report both tied ideas equally, include all justifications.

## State Management

After each phase, update `.mz/task/<task_name>/state.md`. Track current phase, iteration count, votes per round, and participating agents. Persist all ideas and votes in `.mz/task/<task_name>/history.md` for later rounds.

Critical: never proceed past the approval gate without explicit user approval. Never skip voting. Never fabricate votes.
