# Behavior: Critique

Dispatch contract for `/expert` lens panelists. The expert orchestrator reads this file, substitutes `{variables}`, and sends the composed prompt verbatim as the user message to each dispatched lens agent. Do not include this explanation or the outer code fence in the final prompt — only the text inside.

## Template variables

| Variable                | Source                                                                          | Example                                  |
| ----------------------- | ------------------------------------------------------------------------------- | ---------------------------------------- |
| `{brief}`               | `intake.md` contents                                                            | —                                        |
| `{research_block}`      | `research.md` contents if present, else literal text `no codebase research run` | —                                        |
| `{round_n}`             | current round (1, 2, or 3)                                                      | `2`                                      |
| `{prior_summary_block}` | empty for R1; `## Previous round summary\n\n<round_{n-1}_summary.md>` for R2/R3 | —                                        |
| `{prior_iter_block}`    | empty for R1; `## Your prior output\n\n<iter_{n-1}_{agent_name}.md>` for R2/R3  | —                                        |
| `{output_path}`         | absolute path where the agent writes its artifact                               | `.mz/expert/xxx/iter_2_lens-engineer.md` |
| `{lens_name}`           | short lens label, no prefix                                                     | `engineer`                               |
| `{agent_name}`          | full agent name                                                                 | `lens-engineer`                          |

When R1, substitute empty strings for `{prior_summary_block}` and `{prior_iter_block}` and collapse the surrounding blank lines.

## Dispatch prompt body

```text
MODE: critique
OUTPUT: {output_path}
ROUND: {round_n}

## Brief

{brief}

## Research context

{research_block}

{prior_summary_block}

{prior_iter_block}

## How to work

### If ROUND is 1

1. Read the brief and research context.
2. From your lens, produce:
   - 3–5 **strengths** your lens uniquely surfaces
   - 3–5 **weaknesses** your lens uniquely surfaces
   - 2–4 **risks** — failure modes, downstream costs, adversarial scenarios
   - 2–5 **suggestions** — concrete, actionable, from your lens
3. Set Confidence: High | Medium | Low, with one sentence on why.

### If ROUND is 2 or 3

1. Read the prior_summary_block — previous round's neutral synthesis of all 5 panelists.
2. Read the prior_iter_block — your own prior critique from round {round_n} minus 1.
3. React to peers by name when they surfaced something your lens should update on. Hold when your reasoning still applies — principled stagnation is fine.
4. Produce the same four sections (strengths, weaknesses, risks, suggestions) revised in light of the new information.
5. Add a Reactions section: for each peer claim that mattered to you, one sentence referencing the peer by their lens name (e.g., `lens-cto raised cold-start costs I had not considered...`).
6. Add a Changelog: what moved from your prior round and why, or the literal text `no change: <principled reason>`.
7. Update Confidence.

## Critique rules

- Tie every concern to an observable mechanism; quantify where possible.
- Stay in your lens. Reference peers only in Reactions (R2/R3).
- If the brief is thin, downgrade Confidence; do not invent details.

## Output schema

Write the following markdown to the file at OUTPUT.

### When ROUND is 1

# Lens: {lens_name} — critique round 1

## Strengths
- ...

## Weaknesses
- ...

## Risks
- ...

## Suggestions
- ...

## Confidence
High | Medium | Low — one sentence why.

### When ROUND is 2 or 3

# Lens: {lens_name} — critique round {round_n}

## Strengths
- ...

## Weaknesses
- ...

## Risks
- ...

## Suggestions
- ...

## Confidence
High | Medium | Low — one sentence why.

## Reactions
- lens-<peer>: <your reaction referencing their claim by name>

## Changelog
- <what changed from your prior round and why — or "no change: <principled reason>">

## Terminal status line

End your response with exactly one of:

- `STATUS: DONE` — output written, on-lens, all sections present.
- `STATUS: DONE_WITH_CONCERNS` — wrote the file but flagged caveats above this line.
- `STATUS: NEEDS_CONTEXT` — cannot proceed; name the missing input above this line.
- `STATUS: BLOCKED` — unresolvable state.
```

## Orchestrator post-dispatch checklist

1. Verify the file at `{output_path}` was created.
1. Validate structure: Strengths/Weaknesses/Risks/Suggestions/Confidence present (R1); plus Reactions/Changelog (R2/R3).
1. Validate terminal `STATUS:` line in the agent's response — parse it and log.
1. On malformed / empty / wrong STATUS: retry once with a clarified prompt; if still bad, note the gap in `state.md` and downgrade the synthesizer's confidence rating for that agent in that round.
