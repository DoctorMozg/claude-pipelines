# Phases 3-4: Synthesis, Voting, and Report

Detail for the synthesis + voting loop and final report generation.

## Phase 3: Synthesis + Voting

### 3.1 Select a synthesizer

Pick one of the 5 panelists **at random** (different from last round if iterating) to act as the synthesizer for this round. The synthesizer is still a panelist — they vote too.

### 3.2 Dispatch synthesizer

Dispatch the selected personality agent with this prompt:

```
You are the synthesizer for this brainstorming round.

Read the ideas from this round: .mz/task/<task_name>/ideas_round_<N>.md
Read the full history: .mz/task/<task_name>/history.md

Your task:
1. Group related ideas into themes (3-5 themes max)
2. For each theme, write a merged "best version" that combines the strongest elements
3. Identify areas of agreement (ideas multiple panelists converged on)
4. Identify areas of disagreement (conflicting approaches or trade-offs)
5. Produce a ranked shortlist of the top 5 ideas (merged or original) with a 1-sentence pitch for each

Apply your own perspective — you're a <agent lens>, so your synthesis will naturally emphasize your values. This is intentional.

Write the synthesis as structured markdown. Be concise.
```

Save the synthesis to `.mz/task/<task_name>/synthesis_round_<N>.md`.

### 3.3 Dispatch voting round

Load `plugins/mz-creative/skills/brainstorm/behaviors/ideation.md`. Substitute variables per-voter:

| Variable                  | Value                                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `{topic}`                 | the brainstorming topic                                                                          |
| `{round_n}`               | current iteration                                                                                |
| `{previous_rounds_block}` | `## Synthesis\n\n<contents of synthesis_round_<N>.md>\n\n## History\n\n<contents of history.md>` |
| `{output_path}`           | `.mz/task/<task_name>/vote_round_<N>_<agent_name>.md`                                            |
| `{lens_name}`             | short lens label (e.g. `engineer` for `lens-engineer`)                                           |
| `{step}`                  | `vote`                                                                                           |

Dispatch all **PANEL_SIZE** (5) panelists in a **single message** as parallel Agent tool calls. Each receives its own substituted prompt.

### 3.4 Collect and tally votes

Read each voter's file at `{output_path}`. Extract the **Vote**, **Justification**, and (optional) **Objection** fields from each lens's vote artifact.

Build a vote tally:

```markdown
## Round <N> — Votes

| Idea | Votes | Voters |
|---|---|---|
| <idea 1> | 3 | lens-engineer, lens-scientist, lens-economist |
| <idea 2> | 2 | lens-artist, lens-storyteller |

### Justifications
- **lens-engineer**: <reason>
- **lens-artist**: <reason>
[...]

### Objections
- **lens-philosopher** objects to <idea>: <reason>
[...]
```

Append the tally to `.mz/task/<task_name>/history.md`.

### 3.5 Convergence check

**Majority reached** (any idea has >= **MAJORITY_THRESHOLD** votes):

- Record the winning idea, its voters, and all justifications
- Update state: phase → `consensus_reached`, winning_idea → `<name>`
- Proceed to Phase 4

**No majority and iteration < MAX_ITERATIONS**:

- Identify the top 2 ideas and the key disagreement between them
- Write a disagreement summary to state.md: which agents disagree, on what, and why
- Update state: phase → `no_consensus`, iteration remains at N
- **Loop back to Phase 2** (ideation) — the next ideation dispatch will include the history and disagreement context

**No majority and iteration = MAX_ITERATIONS**:

- Record the top 2-3 ideas by vote count across all rounds
- Update state: phase → `max_iterations_reached`
- Proceed to Phase 4 with the best available ideas

## Phase 4: Report

### 4.1 Compile final report

Write the report to `.mz/reports/<YYYY_MM_DD>_brainstorm_<topic_slug>.md` (append `_v2`, `_v3` if exists).

Template:

```markdown
# Brainstorm: <topic>

**Date**: <YYYY-MM-DD>
**Panel**: <5 agent names>
**Iterations**: <count>
**Outcome**: <consensus / best-of-N / max-iterations-exhausted>

## Winning Idea

### <idea name>
<full concept description, merged from all contributions>

**Votes**: <count> / <PANEL_SIZE>
**Supporters**: <agent names with 1-sentence justifications>
**Dissent**: <any objections with reasons>
**Feasibility**: <aggregate signal>

## Runner-Up Ideas

### <idea 2 name>
<concept>
**Votes**: ...
**Supporters**: ...

### <idea 3 name>
<concept>
**Votes**: ...
**Supporters**: ...

## All Ideas by Round

### Round 1
[summary of all ideas from round 1, grouped by agent]

### Round 2 (if applicable)
[summary]

[...]

## Voting History

### Round 1 Votes
[tally table]

### Round 2 Votes (if applicable)
[tally table]

[...]

## Panel Perspectives

Brief final statement from each panelist's lens on the winning idea:

- **<agent 1>**: <1-2 sentences>
- **<agent 2>**: <1-2 sentences>
[...]

## Methodology

- Lenses selected: <5 of 16>
- Selection rationale: <brief>
- Iterations: <count>
- Consensus method: majority vote (>= 3/5)
- Synthesizer rotation: <which agent synthesized each round>
```

### 4.2 Present to user

Update state to `completed`. Present a summary to the user including:

- The winning idea (or top 2-3 if no consensus)
- How many iterations it took
- The report file path
- A one-line take from each panelist
