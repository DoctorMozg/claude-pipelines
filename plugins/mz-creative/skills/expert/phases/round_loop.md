# Phase 2: Round Loop

Full detail for the 3-round consultation loop. Each round is a parallel panelist dispatch followed by a round synthesizer. No early stopping, no convergence check — **always 3 rounds**.

## Goal

Run the 5-member approved panel through 3 structured rounds of critique. Each round produces:

- 5 panelist outputs (`iter_<N>_<agent>.md`)
- 1 neutral synthesis (`round_<N>_summary.md`)

## Constants (from SKILL.md)

- `ROUNDS`: 3 (fixed)
- `PANEL_SIZE`: 5

## Loop structure

```
for N in 1..3:
    2.1 Build per-agent context packet (varies by round — see below)
    2.2 Dispatch all 5 panelists in ONE message (5 parallel Agent calls)
    2.3 Collect iter_<N>_<agent>.md artifacts; retry any malformed once
    2.4 Dispatch expert-round-synthesizer → round_<N>_summary.md
    2.5 Verify summary; update state.md (Round: N)
```

## Step 2.1 — Build context packet from the critique behavior

Load `plugins/mz-creative/skills/expert/behaviors/critique.md`. That file defines the dispatch prompt template with `{variable}` placeholders inside a fenced `text` code block. That block is the entire message to send to each lens agent — nothing before it, nothing after it. You must substitute variables per-agent and per-round before dispatching.

### Per-agent variable substitution

For each of the 5 selected lens agents, substitute:

| Variable                | Value                                                                                    |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| `{brief}`               | verbatim contents of `intake.md`                                                         |
| `{research_block}`      | contents of `research.md` if present, else literal text `no codebase research run`       |
| `{round_n}`             | current round number (1, 2, or 3)                                                        |
| `{prior_summary_block}` | empty for R1; `## Previous round summary\n\n<verbatim round_<N-1>_summary.md>` for R2/R3 |
| `{prior_iter_block}`    | empty for R1; `## Your prior output\n\n<verbatim iter_<N-1>_<agent_name>.md>` for R2/R3  |
| `{output_path}`         | `.mz/task/<task_name>/iter_<N>_<agent_name>.md`                                          |
| `{lens_name}`           | short lens label derived from the agent name (e.g. `engineer` for `lens-engineer`)       |
| `{agent_name}`          | the full agent name (e.g. `lens-engineer`)                                               |

When R1, substitute empty strings for `{prior_summary_block}` and `{prior_iter_block}` and collapse the surrounding blank lines so there is no stray empty section.

## Step 2.2 — Parallel panelist dispatch

Read `.mz/task/<task_name>/panel.md` to get the 5 agent names. Dispatch all 5 in **one message** (single tool-use block with 5 `Agent` calls). Each gets its own substituted dispatch prompt as the user message.

The 5 panelists are opus-class lens agents registered by their `name:` field (e.g., `lens-engineer`, `lens-cto`). Do not repeat agent system-prompt instructions — the critique behavior prompt is self-contained.

Parallelism is load-bearing. Sequential dispatch triples latency and introduces ordering bias. Never serialize.

## Step 2.3 — Collect artifacts

For each panelist, verify:

```bash
test -s .mz/task/<task_name>/iter_<N>_<agent>.md
```

And that the file contains the required sections for the round. Quick check:

```bash
grep -c '^## Strengths\|^## Weaknesses\|^## Risks\|^## Suggestions\|^## Confidence' \
  .mz/task/<task_name>/iter_<N>_<agent>.md
```

Should return ≥ 5 for round 1 and ≥ 7 for rounds 2-3 (adds Reactions + Changelog).

### If an agent output is missing or malformed

- Retry once with a clarified dispatch that explicitly lists the missing sections.
- If the retry still fails, log the gap in `state.md` under a `## Gaps` section and continue the round without that agent's output. Never block a round on a single missing agent.

## Step 2.4 — Dispatch round synthesizer

Once all 5 (or however many succeeded) panelist outputs are on disk, dispatch `expert-round-synthesizer` (model: **sonnet**):

```
You are the round synthesizer for an expert panel review. Your job is a neutral, lens-agnostic consolidation. You do not advocate.

## Task Directory
.mz/task/<task_name>/

## Round
<N>

## Read
- .mz/task/<task_name>/iter_<N>_<agent1>.md
- .mz/task/<task_name>/iter_<N>_<agent2>.md
- ... (all 5 panelist files for round <N>)
- .mz/task/<task_name>/panel.md

## Your Job
Write .mz/task/<task_name>/round_<N>_summary.md using the schema from your agent spec. Capture:

1. **Consensus** — points ≥3 of the 5 agents converged on. Quote or paraphrase specific agents.
2. **Divergence** — explicit conflicts. Name both sides. Capture the core tradeoff.
3. **Key tensions** — 2-3 unresolved tradeoffs the panel is circling.
4. **Emerging recommendations** — actions gaining traction across lenses. Tag which agents endorse each.
5. **Gaps** — important angles no panelist addressed.

## Rules
- Neutral tone. Do not weight any lens.
- Cite agents by name. Never say "the panel thinks" — say "<agent1>, <agent2>, and <agent3> converge on X".
- Do not add your own opinion.
- Be concise. This summary will be read by every agent in the next round; every extra token multiplies.

Terminal status line: STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED
```

### Handle synthesizer status

- `DONE` — proceed to state update.
- `DONE_WITH_CONCERNS` — log concerns, proceed.
- `NEEDS_CONTEXT` — re-dispatch with the missing piece (usually pointing at a file); do not advance round counter.
- `BLOCKED` — escalate to user.

## Step 2.5 — Update state

After each round, update `state.md`:

```
Status: running
Phase: 2
PhaseName: round_<N>_complete
Round: <N>
FilesWritten:
  - ... (append iter_<N>_<agent>.md × 5 and round_<N>_summary.md)
```

Emit a visible round-complete block to the user so they see progress:

```
Round <N>/3 complete.
  Panelists responded: <count>/5
  Summary: round_<N>_summary.md
  Consensus points: <count>
  Divergence points: <count>
  Gaps: <count>
```

## Exit condition

After round 3 completes and `round_3_summary.md` is verified, proceed to Phase 3 (Final Report).

**Do not exit early.** The 3-round count is load-bearing: round 1 surfaces first impressions, round 2 lets the panel react to each other, round 3 gives each panelist a chance to hold or change their final position before the report is written. Cutting short drops the Delphi property.

## Sub-agent status handling (four-status protocol)

Applies to the synthesizer (and researcher in Phase 1). Does **not** apply to panelist agents — panelists do not emit STATUS lines; they emit their structured markdown output and the orchestrator validates the sections.

- `DONE` — proceed.
- `DONE_WITH_CONCERNS` — log and proceed.
- `NEEDS_CONTEXT` — add context, re-dispatch, do not advance.
- `BLOCKED` — escalate, never auto-retry.

## Notes

- The synthesizer is lens-neutral on purpose. Rotating synthesizers (brainstorm's pattern) bias the inter-round context and pull the panel toward whichever lens synthesized.
- Round 3 receives only `round_2_summary.md`, not round 1 summary. The panelist's own prior files carry their self-history. This prevents context bloat.
- If a panelist's round 2 Changelog is empty across all 5 panelists, the panel has saturated — but that is NOT an early-exit signal. Continue to round 3. The report writer can note the saturation if it matters.
- Parallelism discipline: one message per round with all 5 Agent calls. Never serialize.
