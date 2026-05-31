# Phase 2: Discuss — Weight-Scaled Critic Panel

Subject the draft to adversarial review, scaled to the decision's weight. A `heavy` decision earns the full four-lens opus panel plus a synthesizer, looped until it converges; a `light` decision gets one consolidated quick critic whose verdict stands alone. An exempt change (`ARTIFACT: none`) never reaches this phase.

## Inputs (from Phase 1)

- `.mz/task/<task_name>/draft.md` — the populated artifact, the single thing critics read.
- `WEIGHT` (`light` | `heavy`) and the resolved artifact type, recorded in `state.md`.
- `routing.md`, `provenance.md` — available as discussion context.

## Constants (from SKILL.md)

- `MAX_DISCUSS_ITERATIONS`: 3 | `MAX_PANEL_AGENTS`: 4

## Branch on weight

Read `WEIGHT` from `state.md`. `heavy` → run the panel loop (Step H). `light` → run the single quick critic (Step L). Nothing else is valid here — `none` stopped at Phase 1.

______________________________________________________________________

## Step L — Light path (single quick critic)

A simple ADR. Dispatch `gov-critic-quick` (sonnet, read-only). It runs all four lenses itself in one pass and **its `VERDICT:` is the verdict of record** — there is no synthesizer behind it. Single-agent dispatch, no wave manifest. Set `iteration = 1`.

Dispatch prompt (`<N>` is the current iteration):

```
Run the fast governance review on this light-weight decision draft.

## Task Directory
.mz/task/<task_name>/

## Iteration
<N>

## Read
- .mz/task/<task_name>/draft.md
- .mz/task/<task_name>/routing.md   (discussion context)

## Output
Write your consolidated four-lens review to .mz/task/<task_name>/discuss_<N>_quick.md.
End with VERDICT: PASS|FAIL then STATUS:.
```

Read the returned `VERDICT:` and `STATUS:`:

- `VERDICT: PASS` → record `LastVerdict: PASS (light)`, append `discuss_<N>_quick.md` to `FilesWritten`, advance to Phase 3. The gate reads this last iteration's file as the verdict of record.
- `VERDICT: FAIL` → revise `draft.md` against the critic's findings (Step R revision rules), `iteration += 1`, and re-dispatch the quick critic — writing a fresh `discuss_<N>_quick.md` so earlier iterations are preserved — capped at `MAX_DISCUSS_ITERATIONS`. At the cap without PASS, escalate (Step E).
- `STATUS: NEEDS_CONTEXT` / `BLOCKED` → escalate via AskUserQuestion; do not invent a verdict.

Emit a one-line verdict block (`light path iter <N> — VERDICT: <PASS|FAIL>, Critical findings: <count>`). The light path produces no synthesizer file — do not dispatch `gov-discussion-synthesizer`.

______________________________________________________________________

## Step H — Heavy path (four-critic panel loop)

RFD, design doc, or an ADR with three or more options. Set `iteration = 1`.

```
loop:
  H.1  Pre-dispatch manifest, then 4 opus critics in ONE message  → discuss_<N>_<lens>.md
  H.2  Post-wave rollup
  H.3  Dispatch gov-discussion-synthesizer                        → discussion_<N>.md
  H.4  Read AGGREGATE
  H.5  AGGREGATE PASS → exit loop, go to Phase 3
  H.6  FAIL and iteration < MAX → revise draft.md, iteration += 1, go to H.1
  H.7  FAIL and iteration == MAX → escalate via AskUserQuestion (Step E)
```

### H.1 — Manifest, then parallel critic dispatch

Emit the manifest first:

```
Dispatching governance critic panel — 4 agents in parallel
Purpose: adversarial review of draft.md, iteration <N>
- gov-critic-alternatives  — option-space completeness
- gov-critic-reversibility — one-way vs two-way door
- gov-critic-blast-radius  — downstream impact
- gov-critic-assumptions   — load-bearing premises
```

Then spawn **all four agents in one message** (a single tool block with four parallel Agent calls — never sequentially; serial dispatch triples latency and biases ordering). Each is opus, read-only. Per-critic dispatch prompts — identical except the lens, the output path, and the focus line:

**gov-critic-alternatives**

```
Critique this decision draft from the considered-options lens only.

## Task Directory
.mz/task/<task_name>/

## Iteration
<N>

## Read
- .mz/task/<task_name>/draft.md
- .mz/task/<task_name>/routing.md   (discussion context)

## Output
Write findings to .mz/task/<task_name>/discuss_<N>_alternatives.md.
End with VERDICT: PASS|FAIL then STATUS:.
```

**gov-critic-reversibility** — identical, output `discuss_<N>_reversibility.md`, lens "one-way vs two-way door classification".

**gov-critic-blast-radius** — identical, output `discuss_<N>_blast-radius.md`, lens "downstream / dependency impact".

**gov-critic-assumptions** — identical, output `discuss_<N>_assumptions.md`, lens "unstated load-bearing premises".

The four output filenames (`discuss_<N>_alternatives.md`, `discuss_<N>_reversibility.md`, `discuss_<N>_blast-radius.md`, `discuss_<N>_assumptions.md`) are the exact paths the synthesizer reads — keep them verbatim.

### H.2 — Post-wave rollup

Once all four return, emit the rollup before synthesis. The ratio must be exact — a critic that returned no `VERDICT:`/`STATUS:` line is listed as `NO RETURN BLOCK`, never dropped from the count:

```
Wave complete — <returned>/4 critics returned
- gov-critic-alternatives:  <VERDICT> — <≤8 words>
- gov-critic-reversibility: <VERDICT> — <≤8 words>
- gov-critic-blast-radius:  <VERDICT> — <≤8 words>
- gov-critic-assumptions:   <VERDICT> — <≤8 words>
```

If any critic returned `NEEDS_CONTEXT` (a missing path) or `BLOCKED` (unreadable draft), resolve it — re-dispatch that one critic with the corrected path, or escalate a genuine blocker via AskUserQuestion — before synthesizing. Do not synthesize over a missing lens.

### H.3 — Synthesize

Dispatch `gov-discussion-synthesizer` (sonnet). It reads the four critic files and writes `discussion_<N>.md` with the merged action items and one aggregate verdict. Single-agent dispatch.

```
Synthesize this iteration's four governance critics into one verdict.

## Task Directory
.mz/task/<task_name>/

## Iteration
<N>

## Read (the four critic outputs)
- .mz/task/<task_name>/discuss_<N>_reversibility.md
- .mz/task/<task_name>/discuss_<N>_alternatives.md
- .mz/task/<task_name>/discuss_<N>_blast-radius.md
- .mz/task/<task_name>/discuss_<N>_assumptions.md

## Output
Write .mz/task/<task_name>/discussion_<N>.md with the verdict block, merged
action items, and conflicts. End with AGGREGATE: PASS|FAIL then STATUS:.
```

### H.4 — Read the aggregate

Grep the verdict from `discussion_<N>.md`:

```bash
grep -E '^(reversibility|alternatives|blast-radius|assumptions|AGGREGATE):' .mz/task/<task_name>/discussion_<N>.md
```

Emit a visible block:

```
Iteration <N> verdict:
  alternatives:  <PASS|FAIL>
  reversibility: <PASS|FAIL>
  blast-radius:  <PASS|FAIL>
  assumptions:   <PASS|FAIL>
  AGGREGATE:     <PASS|FAIL>
Critical findings: <count>
```

Append `discuss_<N>_*.md` and `discussion_<N>.md` to `FilesWritten`; record the verdict in `state.md` as `LastVerdict`.

### H.5 — AGGREGATE PASS

All four critics passed. Record `phase_complete: true` for Phase 2, save the iteration count, advance to Phase 3.

### H.6 — AGGREGATE FAIL, iteration < MAX

Revise `draft.md` against `discussion_<N>.md` (Step R), `iteration += 1`, loop back to H.1.

### H.7 — AGGREGATE FAIL at MAX

Escalate via AskUserQuestion (Step E).

______________________________________________________________________

## Step R — Orchestrator revises the draft

The orchestrator applies the synthesized action items to `draft.md` itself — small markdown edits, no revision-writer agent (it saves a dispatch and the orchestrator already holds the context). Apply every `Critical:` action item from `discussion_<N>.md` (or the quick critic's findings on the light path); apply `Nit:`/`Optional:` where cheap. Touch only the flagged sections; preserve the rest verbatim. Overwrite `draft.md` in place — never fork a second draft file. Log a one-line change summary to `state.md`.

## Step E — Escalate at the iteration cap

`MAX_DISCUSS_ITERATIONS` reached and still FAIL. This orchestrator (not a subagent) presents this gate using the two-surface plan pattern — the unresolved state as a chat message, then a short selector. Never silently loop past `MAX_DISCUSS_ITERATIONS`.

**Surface 1 — emit the plan message.** Read the final verdict file and emit the verdict block plus the unresolved `Critical:` findings verbatim as an ordinary markdown chat message:

```
## Discuss panel hit the iteration cap — govern

The draft reached <MAX> discuss iterations with unresolved findings (from discussion_<N>.md or discuss_<N>_quick.md).

### Final verdict

<verbatim verdict block>

### Unresolved Critical findings

<verbatim unresolved Critical: findings>

---
**Accept with unresolved** → carry the open findings into the sign-off gate as caveats  ·  **Abort** → mark aborted, nothing written to docs/  ·  reply with guidance to revise once more
```

**Surface 2 — call AskUserQuestion.** A short selector — the findings live in the message above:

- question: `The discuss panel hit its iteration cap. How should I proceed?`
- options: **Accept with unresolved** — carry the open findings into the sign-off gate as caveats · **Abort** — mark the task aborted, write nothing

Two named options; guidance rides the free-text reply field.

**Response handling:**

- **Accept with unresolved** → record `LastVerdict` as `accepted_with_unresolved`, carry the open findings forward as caveats into Phase 3, advance.
- **Abort** → `Status: aborted_by_user`, stop. Leave all files on disk.
- **Any other reply (guidance)** → take the user's text as the action list, revise `draft.md` once (Step R), then go straight to Phase 3 — no further critique round; the user's word is final.

## Notes

- Critic parallelism on the heavy path is load-bearing — the four critics are fully independent and go in one message. The synthesizer is the only agent that writes `discussion_<N>.md`; critics never write that filename.
- Critics emit `VERDICT:` (not the four-status `STATUS:` protocol for their verdict line, though they close with `STATUS:` too). The synthesizer and quick-critic verdicts both fail closed: a missing `VERDICT:` line counts as FAIL, never an assumed PASS.
- The draft is revised by the orchestrator between iterations; the critics are strictly read-only. One `draft.md`, overwritten in place each round.
- Convergence is zero `Critical:` across all lenses — `Nit:`/`Optional:`/`FYI:` never block the loop.
- On resume into Phase 2, the discuss loop restarts from iteration 1 — earlier `discuss_<N>_*.md` files are left on disk, but a fresh wave is dispatched (the draft may have changed since). A heavy decision therefore re-spends its critic panel on resume; this is intentional and stays bounded by `MAX_DISCUSS_ITERATIONS`.
