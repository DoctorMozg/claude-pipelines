# Behavior: Ideation

Dispatch contract for `/brainstorm` lens panelists. The brainstorm orchestrator reads this file, substitutes `{variables}`, and sends the composed prompt verbatim as the user message to each dispatched lens agent. Do not include this explanation or the outer code fence in the final prompt — only the text inside.

## Template variables

| Variable                  | Source                                             | Example                                                             |
| ------------------------- | -------------------------------------------------- | ------------------------------------------------------------------- |
| `{topic}`                 | user's brainstorming topic                         | `how to onboard B2B users faster`                                   |
| `{round_n}`               | current iteration number                           | `1`                                                                 |
| `{previous_rounds_block}` | empty for round 1; formatted history for round > 1 | —                                                                   |
| `{output_path}`           | absolute path where the agent writes its artifact  | `.mz/task/2026_04_20_brainstorm_xxx/ideas_round_1_lens-engineer.md` |
| `{lens_name}`             | short lens label, no prefix                        | `engineer`                                                          |
| `{step}`                  | `generate` or `vote`                               | `generate`                                                          |

When `{previous_rounds_block}` is empty (round 1 generation), substitute an empty string and collapse the surrounding blank line. When present, format as `## Previous rounds\n\n<history.md contents>`.

## Dispatch prompt body

```text
MODE: ideation
STEP: {step}
OUTPUT: {output_path}
ROUND: {round_n}

TOPIC: {topic}

{previous_rounds_block}

## How to work

### If STEP is "generate"

1. Apply your lens to the topic.
2. Optionally use WebSearch or WebFetch for data, trends, or precedent. Prioritize original thinking over research.
3. Generate 2–3 distinct ideas only someone with your lens would produce.
4. For each idea: name memorably, describe the concept, explain why your lens produces it, assess feasibility.
5. If previous rounds are present above, cite which prior ideas you extend or challenge by title.

### If STEP is "vote"

1. Read the synthesis in the previous_rounds_block.
2. Vote for the single idea that best serves the overall goal from your lens.
3. Justify in one sentence from your perspective.
4. Note any strong objection to another idea (optional).

Keep voting output under 10 lines.

## Output schema

Write the following markdown to the file at OUTPUT.

### When STEP is "generate"

# Lens: {lens_name} — ideation round {round_n}

## Idea 1: <short memorable title>
- **Concept**: 2–3 sentences describing the idea.
- **Why this lens**: 1 sentence on why your perspective produces it.
- **Feasibility**: High | Medium | Low — brief justification.

## Idea 2: <short memorable title>
- **Concept**: ...
- **Why this lens**: ...
- **Feasibility**: ...

## Idea 3: <optional — only if you have a genuinely distinct third>
- **Concept**: ...
- **Why this lens**: ...
- **Feasibility**: ...

### When STEP is "vote"

# Lens: {lens_name} — round {round_n} vote

- **Vote**: <title of chosen idea>
- **Justification**: <one sentence from your lens>
- **Objection**: <optional; omit if none>

Be concise. Token count matters.
```

## Orchestrator post-dispatch checklist

1. Verify the file at `{output_path}` was created.
1. Validate structure: at least one `## Idea` block (when STEP=generate) or a `**Vote**` line (when STEP=vote).
1. On malformed / empty: retry once with a clarified prompt.
1. On second failure: note the gap in `state.md` and exclude the agent from that iteration.
