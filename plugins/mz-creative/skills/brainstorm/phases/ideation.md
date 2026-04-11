# Phase 2: Ideation

Dispatch the 5 selected lens agents in parallel using the ideation behavior contract.

## 2.1 Load the behavior contract

Read `plugins/mz-creative/skills/brainstorm/behaviors/ideation.md`. This file defines the dispatch prompt template with `{variable}` placeholders inside a fenced `text` code block. That block is the entire message to send to each lens agent — nothing before it, nothing after it. You must substitute variables per-agent before dispatching.

## 2.2 Prepare per-agent context

Read `.mz/task/<task_name>/panel.md` to get the 5 selected `lens-*` agents.

For each selected agent, substitute the behavior template variables:

| Variable                  | Value                                                                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `{topic}`                 | the brainstorming topic                                                                                                                       |
| `{round_n}`               | current iteration number (1 for first round)                                                                                                  |
| `{previous_rounds_block}` | empty string for round 1; `## Previous rounds\n\n<contents of history.md>\n\n## Facilitator guidance\n\n<disagreement summary>` for round > 1 |
| `{output_path}`           | `.mz/task/<task_name>/ideas_round_<N>_<agent_name>.md` (absolute or repo-relative)                                                            |
| `{lens_name}`             | the short label derived from the agent name (e.g. `engineer` for `lens-engineer`)                                                             |
| `{step}`                  | `generate`                                                                                                                                    |

When `{previous_rounds_block}` is empty, collapse the surrounding blank line so the prompt does not contain a stray empty section.

## 2.3 Dispatch agents in parallel

Dispatch all **PANEL_SIZE** (5) selected lens agents in a **single message** as parallel Agent tool calls. Each agent receives its own substituted dispatch prompt as the user message. Use each agent's registered name (`lens-engineer`, `lens-artist`, `lens-philosopher`, `lens-mathematician`, `lens-scientist`, `lens-economist`, `lens-storyteller`, `lens-futurist`, `lens-psychologist`, `lens-historian`, `lens-cto`, `lens-data`, `lens-devops`, `lens-product`, `lens-security`, `lens-seo`) as the `subagent_type`.

Do not repeat the agent's system prompt instructions — the behavior prompt is self-contained.

## 2.4 Collect results

Each agent writes its artifact to `{output_path}`. After dispatch, for each agent:

1. Verify the file exists and is non-empty.
1. Validate structure: at least one `## Idea` block with a title, concept, lens rationale, and feasibility signal.
1. If the file is missing, empty, or off-topic: retry once with a clarified prompt per the behavior post-dispatch checklist. If still bad, exclude the agent from this iteration and note the gap in `state.md`.

Merge all agent outputs into `.mz/task/<task_name>/ideas_round_<N>.md`:

```markdown
# Ideas — Round <N>

## lens-engineer

<contents of ideas_round_<N>_lens-engineer.md — skip the agent's own H1 title>

## lens-artist

<contents of ideas_round_<N>_lens-artist.md — skip the agent's own H1 title>

[repeat for each agent that produced output]
```

Append a summary to `.mz/task/<task_name>/history.md`:

```markdown
## Round <N> — Ideation

### lens-engineer

- Idea: <title 1> — <one-line summary>
- Idea: <title 2> — <one-line summary>

[repeat for each agent]

Total ideas this round: <count>
Cumulative ideas: <total across all rounds>
```

Update state: phase → `ideation_complete`, iteration → N.
