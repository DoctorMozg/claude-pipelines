# Phase 3: Critique Loop

Full detail for the critique-loop phase. Covers parallel dispatch of four specialist critics per iteration, synthesis, revision, and exit conditions.

## Goal

Iterate the draft until all four critics return `VERDICT: PASS` and the accessibility-specialist returns `WCAG_GATE: PASS`, or until `MAX_DESIGN_ITERATIONS` is hit.

## Constants (from SKILL.md)

- `MAX_DESIGN_ITERATIONS`: 5

## Initial state

Set `iteration = 1`.

## Loop structure

```
loop:
  3.1  Dispatch 4 critics in parallel   → iter_<N>_*.md
  3.2  Dispatch synthesizer             → critique_<N>.md
  3.3  Read verdict block
  3.4  If AGGREGATE PASS → exit loop, go to Phase 4
  3.5  If FAIL and iteration < MAX → dispatch revision writer, iteration += 1, go to 3.1
  3.6  If FAIL and iteration == MAX → escalate via AskUserQuestion
```

## Step 3.1 — Parallel critic dispatch

Spawn **four agents in one message** (single tool-use block with four Agent calls):

### ui-designer

Model: **opus**. Prompt:

```
You are critiquing a design draft from a visual-composition lens.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/design.md
- .mz/design/<task_name>/wireframes.md

## Your Lens
Layout, grid, alignment, whitespace, visual hierarchy, density, scannability, balance, consistency. See your agent spec for detailed criteria.

## Output
Write to .mz/design/<task_name>/iter_<N>_ui-designer.md using the format from your agent spec. End with `VERDICT: PASS` or `VERDICT: FAIL`.
```

### ux-designer

Model: **opus**. Prompt:

```
You are critiquing a design draft from a UX flow and heuristics lens.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/design.md
- .mz/design/<task_name>/wireframes.md

## Reference
Grep plugins/mz-design/skills/design-document/references/nielsen-heuristics.md for any heuristic you apply. Do not load the whole file.

## Your Lens
Task flows, IA, interaction patterns, microcopy, state coverage, cognitive load, Nielsen's 10 heuristics. See your agent spec for detailed criteria.

## Output
Write to .mz/design/<task_name>/iter_<N>_ux-designer.md using the format from your agent spec. End with `VERDICT: PASS` or `VERDICT: FAIL`.
```

### art-designer

Model: **opus**. Prompt:

```
You are critiquing a design draft from a color, type, and mood lens.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/design.md (focus on §6 Color System and §7 Typography)

## Your Lens
Color harmony (complementary, analogous, triadic, split-complementary, tetradic, monochromatic), palette balance, semantic color clarity, type pairing, type scale musicality, weight distribution, mood coherence. See your agent spec for detailed criteria.

## Output
Write to .mz/design/<task_name>/iter_<N>_art-designer.md using the format from your agent spec. End with `VERDICT: PASS` or `VERDICT: FAIL`.
```

### accessibility-specialist

Model: **opus**. Prompt:

```
You are critiquing a design draft from a WCAG 2.2 AA lens and owning the WCAG hard gate.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/design.md (focus on §6 Color System, §11 States, §12 Accessibility)
- .mz/design/<task_name>/wcag-report.md

## Reference
Grep plugins/mz-design/skills/design-document/references/wcag-contrast-thresholds.md for thresholds and the contrast formula.

## Your Job
1. Re-compute every contrast ratio in wcag-report.md from scratch using the WCAG formula.
2. Emit `CONFLICT DETECTED:` if any reported ratio disagrees with your computation by more than 0.05.
3. Verify every text/background pair actually used in the design is present in the report. Missing pairs = `Critical:` finding.
4. Check keyboard nav, focus management, screen-reader semantics specifications.
5. Emit both `VERDICT: PASS|FAIL` (per-critic) and `WCAG_GATE: PASS|FAIL` (hard gate) on separate lines.

## Output
Write to .mz/design/<task_name>/iter_<N>_accessibility-specialist.md using the format from your agent spec.
```

All four critics are fully independent — they must be dispatched as **one message with four parallel Agent tool calls**, not sequentially.

## Step 3.2 — Synthesize

Once all four critics return, spawn `design-critique-synthesizer` (model: **sonnet**):

```
You are synthesizing four critic outputs into a single action-item list and aggregate verdict.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/iter_<N>_ui-designer.md
- .mz/design/<task_name>/iter_<N>_ux-designer.md
- .mz/design/<task_name>/iter_<N>_art-designer.md
- .mz/design/<task_name>/iter_<N>_accessibility-specialist.md

## Your Job
Merge findings, resolve conflicts with lane ownership, compute the verdict block, and write .mz/design/<task_name>/critique_<N>.md using the format from your agent spec.
```

## Step 3.3 — Read verdict block

Grep the verdict block from `critique_<N>.md`:

```bash
grep -E '^(ui-designer|ux-designer|art-designer|accessibility-specialist|WCAG_GATE|AGGREGATE):' .mz/design/<task_name>/critique_<N>.md
```

Parse the 6 lines. Store each PASS/FAIL value.

Emit a visible block:

```
Iteration <N> verdict:
  ui-designer:              <PASS|FAIL>
  ux-designer:              <PASS|FAIL>
  art-designer:             <PASS|FAIL>
  accessibility-specialist: <PASS|FAIL>
  WCAG_GATE:                <PASS|FAIL>
  AGGREGATE:                <PASS|FAIL>

Critical findings: <count>
```

## Step 3.4 — Handle AGGREGATE PASS

If `AGGREGATE: PASS` (all four critics PASS **and** WCAG_GATE PASS):

- Update state to `critique_passed`, save iteration count.
- Exit the loop, proceed to Phase 4 (Finalization).

## Step 3.5 — Handle AGGREGATE FAIL (iteration < MAX)

If any verdict is FAIL and `iteration < MAX_DESIGN_ITERATIONS`:

### 3.5.1 Dispatch the revision writer

Spawn `design-revision-writer` (model: **opus**) with:

```
You are applying critique action items to the current design draft.

## Task Directory
.mz/design/<task_name>/

## Iteration
<N>

## Read
- .mz/design/<task_name>/design.md
- .mz/design/<task_name>/wireframes.md
- .mz/design/<task_name>/wcag-report.md
- .mz/design/<task_name>/critique_<N>.md

## Your Job
Apply every action item in critique_<N>.md. Touch only the flagged sections. Preserve untouched sections verbatim. If any §6 Color System hex value changes, regenerate wcag-report.md from scratch. Emit a change log and terminal STATUS: line per your agent spec.
```

### 3.5.2 Handle revision writer status

- `DONE` or `DONE_WITH_CONCERNS` → `iteration += 1`, loop back to Step 3.1.
- `NEEDS_CONTEXT` → escalate the specific missing piece via `AskUserQuestion`, then re-dispatch the revision writer with added context. Do not increment iteration on context re-dispatch.
- `BLOCKED` → escalate to the user immediately. Offer options: accept current state, provide guidance, abort.

## Step 3.6 — Handle AGGREGATE FAIL at MAX iterations

If `iteration == MAX_DESIGN_ITERATIONS` and AGGREGATE is still FAIL:

Present to the user via `AskUserQuestion`:

```
The design has hit the 5-iteration critique cap and still has unresolved findings.

Final verdict:
  ui-designer:              <status>
  ux-designer:              <status>
  art-designer:             <status>
  accessibility-specialist: <status>
  WCAG_GATE:                <status>

Unresolved findings are in .mz/design/<task_name>/critique_5.md.

How should we proceed?

Reply 'accept' to finalize the current state, 'guidance' to provide specific direction for one more round, or 'abort' to stop.
```

Options:

- **accept** → log unresolved findings into `final-summary.md`, mark state `complete_with_unresolved`, proceed to Phase 4 with the caveat noted.
- **guidance** → accept user feedback as the action list, dispatch the revision writer with the user's text, then go to Phase 4 directly (no further critique round — the user's word is final).
- **abort** → mark state `aborted_by_user`, stop.

Never silently loop past iteration 5.

## Sub-agent status handling

Four-status protocol applies to writer/revision-writer/synthesizer outputs (not critics, which emit VERDICT lines):

- `DONE` — proceed.
- `DONE_WITH_CONCERNS` — log to state.md and proceed.
- `NEEDS_CONTEXT` — re-dispatch with added context, do not increment loop counter.
- `BLOCKED` — escalate, never auto-retry.

Critics emit `VERDICT: PASS|FAIL` (and `WCAG_GATE:` for accessibility-specialist). They do not use the STATUS: protocol.

## State updates per iteration

After each loop step, update `state.md`:

```
Status: running
Phase: 3
PhaseName: critique_loop
Iteration: <N>
LastVerdict: |
  ui-designer:              <status>
  ux-designer:              <status>
  art-designer:             <status>
  accessibility-specialist: <status>
  WCAG_GATE:                <status>
  AGGREGATE:                <status>
FilesWritten:
  - ... (append critique_<N>.md and iter_<N>_*.md paths)
```

## Notes

- Critic parallelism is load-bearing. Sequential critic dispatch triples latency and introduces ordering bias — never serialize them.
- The synthesizer is the only agent that writes `critique_<N>.md`. Do not let critics write to that filename.
- The revision writer is the only agent that modifies `design.md`, `wireframes.md`, and `wcag-report.md` inside the loop. Critics are read-only.
- `WCAG_GATE` is a separate axis from `VERDICT`. A critic can PASS (no Critical findings in its lane) while the accessibility-specialist's WCAG hard gate still FAILs — treat both axes independently when parsing.
