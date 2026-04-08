# Phase 2: Ideation

Detail for the parallel personality agent dispatch and idea collection.

## 2.1 Prepare context packet

Read `.mz/task/<task_name>/panel.md` to get the 5 selected agents.

For the **first iteration**, the context packet per agent is:

```
Topic: <the brainstorming topic>
Your role: <agent name> — <one-line lens description from panel.md>

Generate 2-3 distinct ideas from your unique perspective. For each idea:
1. **Name**: a short memorable title (3-5 words)
2. **Concept**: 2-3 sentences describing the idea
3. **Why this lens**: 1 sentence on why your perspective makes this idea unique
4. **Feasibility signal**: High / Medium / Low with brief justification

You may use WebSearch and WebFetch to research the topic if you need external context, trends, or data to ground your ideas. Prioritize original thinking over research — use research to validate or enrich, not to substitute for creativity.

Write your ideas as a structured markdown list. Be concise — output tokens are expensive.
```

For **subsequent iterations** (iteration > 1), append to the context packet:

```
## Previous rounds

<contents of .mz/task/<task_name>/history.md>

## Facilitator guidance

The panel did not reach consensus in the previous round. Key areas of disagreement:
<disagreement summary from state.md>

Build on the strongest ideas from previous rounds. You may refine an existing idea, combine ideas, or propose something new that bridges the disagreement. Do not simply repeat your prior submission.
```

## 2.2 Dispatch agents in parallel

Dispatch all **PANEL_SIZE** (5) agents in a **single message** as parallel Agent tool calls. Each agent receives the context packet above.

The agents are dispatched using their registered names (e.g., `creative-engineer`, `creative-artist`). The dispatch prompt is the context packet — do not repeat the agent's system prompt instructions.

## 2.3 Collect results

As agents complete, read each agent's response. For each:

1. Extract the structured ideas (name, concept, lens justification, feasibility)
1. Validate: at least 1 idea returned, ideas relate to the topic
1. If an agent returned empty or off-topic: retry once with a clarified prompt. If still empty, note the gap.

Write all collected ideas to `.mz/task/<task_name>/ideas_round_<N>.md`:

```markdown
# Ideas — Round <N>

## <Agent Name>

### Idea 1: <title>
- **Concept**: ...
- **Why this lens**: ...
- **Feasibility**: ...

### Idea 2: <title>
- **Concept**: ...
- **Why this lens**: ...
- **Feasibility**: ...

[repeat for each agent]
```

Append a summary to `.mz/task/<task_name>/history.md`:

```markdown
## Round <N> — Ideation

### <Agent 1 Name>
- Idea: <title 1> — <one-line summary>
- Idea: <title 2> — <one-line summary>

[repeat for each agent]

Total ideas this round: <count>
Cumulative ideas: <total across all rounds>
```

Update state: phase → `ideation_complete`, iteration → N.
