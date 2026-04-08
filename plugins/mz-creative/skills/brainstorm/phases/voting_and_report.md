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

Dispatch all **PANEL_SIZE** (5) panelists in a **single message** as parallel Agent tool calls. Each receives:

```
Voting round <N> for brainstorming topic: <topic>

Read the synthesis: .mz/task/<task_name>/synthesis_round_<N>.md
Read the full history: .mz/task/<task_name>/history.md

The synthesizer (<synthesizer name>) produced a ranked shortlist of top 5 ideas.

Your vote:
1. Pick your #1 idea from the shortlist (by name)
2. Write 1 sentence explaining why from your perspective as a <agent lens>
3. Optionally: note any strong objection to another idea (1 sentence max)

Format:
VOTE: <idea name>
REASON: <1 sentence>
OBJECTION: <idea name> — <1 sentence> (or "none")
```

### 3.4 Collect and tally votes

Read each agent's response. Extract the VOTE, REASON, and OBJECTION fields.

Build a vote tally:

```markdown
## Round <N> — Votes

| Idea | Votes | Voters |
|---|---|---|
| <idea 1> | 3 | engineer, scientist, economist |
| <idea 2> | 2 | artist, storyteller |

### Justifications
- **engineer**: <reason>
- **artist**: <reason>
[...]

### Objections
- **philosopher** objects to <idea>: <reason>
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

Write the report to `.mz/reports/brainstorm_<YYYY_MM_DD>_<topic_slug>.md` (append `_v2`, `_v3` if exists).

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

- Personalities selected: <5 of 10>
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
