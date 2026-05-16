# Phases 2-3: Profile & Hypothesize

**Goal**: Convert the trusted baseline into a ranked, falsifiable hypothesis backlog. Phase 2 profiles the target and isolates the single dominant bottleneck; Phase 3 turns that bottleneck into 3-6 predictions the candidate loop can falsify by measurement.

These two phases share a file because they are one analytical pass — Phase 2 produces the profile, Phase 3 consumes it. **No code or artifact changes happen in either phase.** This is observation and reasoning; the first change to the target is a Phase 4 candidate.

The optimization toolkit is the shared vocabulary for both phases. Grep `references/optimization-toolkit.md` per section — never load the whole file:

- Phase 2 reads **Bottleneck taxonomy** (to classify) and **Profiling principles** (to read the profile correctly).
- Phase 3 reads **Transformation catalog** (to generate hypotheses) and **Prioritization** (to rank them).
- **Anti-patterns** is the standing checklist for both.

## Phase 2: Profile & Classify the Bottleneck

### 2.1 Gather context

Dispatch `pipeline-researcher` to map the target before profiling it:

```
Research context for a performance-optimization profiling pass.

Target system:   <target_system from contract.md>
Target type:     <target_type>
Metric:          <metric_name> (<metric_unit>), direction <metric_direction>
Scope files:     .mz/task/<task_name>/scope_files.txt

Report:
1. How the target is structured — entry points, hot modules, the call / dependency
   path the metric exercises.
2. What profiling or instrumentation the project already has — benchmark harnesses,
   tracing, counters, existing measurement scripts.
3. For any domain you are not confident about, research current profiling and
   optimization best practice with WebFetch / WebSearch and cite the sources.

Do not profile and do not change anything — this is a context-gathering pass.
```

For a `target_type` outside confident training coverage — an unusual runtime, a niche framework, a domain-specific system — the web-research arm of this dispatch is mandatory, not optional. A live best-practice source beats a stale guess. The live profile from §2.2 stays the primary signal regardless of what the research returns.

### 2.2 Profile the target

Profile with a technique the orchestrator selects for `target_type` and `metric_name`, guided by the toolkit's **Profiling principles** section and the tooling §2.1 found. The profile must **attribute the metric across the target's components** — show where the time, space, or cost actually goes — not merely re-confirm the metric's total.

Principles that govern reading the profile (grep the toolkit for the full list):

- Read **self-time**, not total width — a unit that looks wide in the profile because its callees are slow is not itself the bottleneck.
- **Off-CPU time is real time** — blocked, waiting, and queued time count; a CPU-only profiler misses I/O- and contention-bound work.
- One **stable metric** guides the loop — the contract's `metric_name`; never switch metrics mid-run.

Write the profile to `.mz/task/<task_name>/profile.md`: the attribution breakdown, the profiling technique used, and the raw profiler output or a path to it.

### 2.3 Component attribution — `target_type: system` only

A `system` target carries one end-to-end metric but several components (per the contract's domain-tagged `change_space`). Before drilling into any one component, attribute the end-to-end metric **across** components — by time-division, span tracing, or per-component measurement — and write the split to `profile.md`.

Then select the **single dominant component** and profile *inside it* (back to §2.2) for the component-level bottleneck. Phase 3 forms hypotheses only from that component's change classes. Because Phase 6 re-profiles every iteration, the bottleneck is free to move to another component — and another domain — next iteration; that is expected, not an error.

### 2.4 Identify the single dominant bottleneck

From the profile, name the **one** bottleneck that owns the largest attributable share of the metric. One — not a list. The candidate loop optimizes one thing per iteration so each measured delta has one cause.

### 2.5 Classify the bottleneck

Classify it against the toolkit's **Bottleneck taxonomy** — compute-bound, memory-bound, I/O-bound, contention/lock-bound, algorithmic, or config/parameter-bound. The class scopes which transformation classes Phase 3 may draw from: an I/O-bound bottleneck is not addressed by a compute micro-optimization.

### 2.6 Confirm — a counter spike is a hypothesis, not a verdict

A spiking counter, a hot line, a red span — each is a *candidate* bottleneck, not a confirmed one. Before Phase 3, confirm the named bottleneck owns a **proportional share of the metric**: the time, space, or cost attributed to it must be large enough that removing it could plausibly move the metric toward the target. A function that is 3% of runtime cannot deliver a 2x speedup no matter how much it improves (see Amdahl-bounding, §3.2).

If the profile is inconclusive — no component owns a clear majority share, or attribution is too noisy to trust — say so and re-profile with a different technique before proceeding. Do not pick a bottleneck just to have one.

## Phase 3: Hypothesis Generation & Prioritization

### 3.1 Generate 3-6 falsifiable hypotheses

For the confirmed bottleneck, generate 3-6 hypotheses. Each draws a transformation class from the toolkit's **Transformation catalog** and from the contract's `change_space`; a hypothesis whose class is not in `change_space` is allowed only if it is flagged for the Phase 4.5 boundary pause.

Each hypothesis is **falsifiable** — a prediction written *before* the experiment, in this shape:

> Changing **X** to remove mechanism **Y** should improve **\<metric>** by ≈**Z%**.

and carries:

- **Mechanism** — the specific inefficiency the change removes, taken from the profile, not from intuition.
- **Predicted speedup** — a number or range, Amdahl-bounded (§3.2).
- **Confidence** — from evidence strength: how directly the profile supports the mechanism. High = the profile shows the mechanism plainly; low = plausible but indirect. Not a gut feeling.
- **Effort** — rough implementation cost.
- **Risk** — behavioral-regression risk and blast radius.
- **Transformation class** — the `change_space` / catalog class it belongs to.

### 3.2 Amdahl-bound every predicted speedup

A hypothesis can never beat the share of the metric its bottleneck owns. If the bottleneck is 40% of runtime, eliminating it *entirely* caps the end-to-end speedup at 1.67x — and a hypothesis that merely improves it predicts far less. Cap every predicted speedup at this bound. A prediction above the Amdahl bound is an arithmetic error — correct it before ranking.

### 3.3 Rank by impact × confidence ÷ effort

Score each hypothesis `impact × confidence ÷ effort`, where `impact` is the Amdahl-bounded predicted gain. Rank highest-first. The toolkit's **Prioritization** section is the reference: the hottest bottleneck is not always the highest-ranked hypothesis — a smaller, high-confidence, low-effort win can outrank a large, speculative, expensive one.

### 3.4 Write the backlog

Write the ranked list to `.mz/task/<task_name>/backlog.md`:

```markdown
# Hypothesis Backlog — <task_name>

Bottleneck: <name> (<class>, <share>% of <metric>)
Profile:    .mz/task/<task_name>/profile.md

## Ranked hypotheses

### H1 — <one-line title>   [score <S>]
- Prediction: changing <X> to remove <Y> should improve <metric> by ≈<Z>%
- Mechanism:  <the inefficiency removed>
- Predicted:  <Z>%   (Amdahl bound: <bound>)
- Confidence: <high|medium|low> — <evidence>
- Effort:     <low|medium|high>
- Risk:       <low|medium|high> — <blast radius>
- Class:      <transformation class>   [in change_space: yes|no]

### H2 — ...
```

### 3.5 Record and proceed

- Update `state.md`: `Phase: 3`, `PhaseName: hypothesize`, the bottleneck name and class, and the backlog hypothesis count.
- Mark the Phase 2 and Phase 3 task trackers done.

Phases 2 and 3 are complete. Return to `SKILL.md` for the **Phase 3.5 Backlog / Strategy Approval** gate — the user approves the strategy before any candidate code is written.
