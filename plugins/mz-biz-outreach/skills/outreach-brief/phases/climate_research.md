# Phase 2: Local-Climate Research

Read `SKILL.md` first. This phase picks up after the brief is approved at Phase 1.5. It runs two agent waves per industry × region combo, then synthesizes the dossier inline. All research agents are writers — never dispatch with `run_in_background: true`, and never exceed `MAX_AGENTS_PER_WAVE` (6) concurrent agents per assistant message.

## 2.0 Build and cap the combo list

Read `.mz/outreach/<run_name>/brief.json`, then build the research set in four explicit steps:

1. **Form** the cross-product of `icp.industries` × `geography.target_regions`, iterating industries in brief order (outer loop) and regions in brief order (inner loop). Brief order *is* priority order — the user lists the most important industries and regions first, so the earliest combos are the most important.
1. **Filter** out any pair matched by `goal_channels_voice.exclusions`.
1. **Slug** each surviving combo as `<industry_slug>__<region_slug>` (snake_case, each side max 20 chars) and de-duplicate.
1. **Cap** at `MAX_CLIMATE_COMBOS` (20): keep the first 20 in priority order. If any combos remain beyond 20, they are truncated — emit a one-line disclosure listing every dropped combo by name and record the dropped set in the `## Decisions` section of `state.md`. Never drop a combo silently.

Research the kept combos (≤ 20) in sequential waves of `MAX_AGENTS_PER_WAVE` (6): the wave size is the concurrency cap, and as many waves run as needed to cover every kept combo. State the combo count before Wave A so the user sees the research scope.

## 2.1 Wave A — source discovery

Emit the pre-dispatch manifest before dispatching:

```
Dispatching climate source discovery — <N> agents in parallel
  outreach-climate-source-finder — <industry> × <region>
  …one line per combo in this wave
```

Spawn one `outreach-climate-source-finder` per combo (waves of ≤6, foreground):

```
Find the best local business-climate sources for this market:
Industry: <industry>
Region: <region>
Signal types to cover: economic & market trends, regulatory & policy shifts, industry deals & news, sector pain points & demand drivers
Write your ranked source list to: <RUN_DIR>/_climate_sources/<combo_slug>.json
```

After each wave, emit the post-wave rollup — never silently drop an agent:

```
Wave complete — <returned>/<dispatched> agents returned
  <industry> × <region>: <STATUS> — <≤8-word summary>
  …one line per agent; an agent with no/malformed STATUS line is "NO RETURN BLOCK"
```

Update `.mz/task/<task_name>/state.md` `Phase` to `climate_sources_complete`.

## 2.2 Wave B — climate research

Emit the pre-dispatch manifest, then spawn one `outreach-climate-researcher` per combo (waves of ≤6, foreground):

```
Research the local business climate for this market:
Industry: <industry>
Region: <region>
Ranked sources: <RUN_DIR>/_climate_sources/<combo_slug>.json
Recency window (months): <RECENCY_MONTHS>
Cover all four signal types: economic, regulatory, deals, pain_points. Derive 3–5 outreach angles tied to named signals.
Write your climate JSON to: <RUN_DIR>/_climate/<combo_slug>.json
```

Emit the post-wave rollup as in 2.1. If a combo's source-discovery returned `BLOCKED` or empty, still dispatch its researcher (it falls back to its own sourcing) but note the thin input. Update `state.md` `Phase` to `climate_research_complete`.

## 2.3 Synthesize the dossier (inline — no subagent)

Read every `<RUN_DIR>/_climate/<combo_slug>.json`. Build the two permanent artifacts.

`.mz/outreach/<run_name>/climate.json`:

```json
{
  "run_name": "<run_name>",
  "recency_months": <RECENCY_MONTHS>,
  "combos": [ <verbatim per-combo climate object>, ... ],
  "regional_summary": "Cross-cutting read across all combos — shared trends, divergences, the dominant climate story.",
  "proposal_hooks": [
    { "industry": "...", "region": "...", "angle": "...", "based_on": ["<signal title>", ...] }
  ]
}
```

`proposal_hooks` aggregates the strongest `top_outreach_angles` across combos — this is the list the downstream proposal step reads.

`.mz/outreach/<run_name>/climate.md` — the human dossier:

- One `##` section per industry × region combo: the four signal groups (each item dated, with its link and outreach implication), the combo's `overall_climate`, and its outreach angles.
- A `## Regional summary` section with the cross-cutting read.
- A `## Proposal hooks` section listing every hook with the combo it serves and the signals it rests on.

## 2.4 Finish

1. Delete the temp directories `<RUN_DIR>/_climate_sources/` and `<RUN_DIR>/_climate/`.
1. Update `.mz/task/<task_name>/state.md`: set `Phase` to `complete`, `Status` to `complete`, `phase_complete: true`, `what_remains: []`. Append a `## Decisions` section recording that the brief was approved and listing the combos researched.
1. Emit the verification block required by `SKILL.md`: run name, absolute paths of `brief.md` and `climate.md`, combo count, and per-combo signal counts. Confirm both artifact pairs exist and the temp folders are gone.
1. Hand off: tell the user the run is ready and how to use it —
   - `/outreach-research brief:<run_name>` to discover companies with the climate folded into strategy, and
   - `/outreach-enrich-company <card> brief:<run_name>` to draft proposals that lead with local-climate hooks.
