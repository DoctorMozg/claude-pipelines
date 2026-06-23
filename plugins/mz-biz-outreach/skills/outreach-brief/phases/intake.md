# Phase 1: Intake — Iterative Clarification Loop

Read `SKILL.md` first. This phase is run by **the orchestrator**, interactively — it must not be delegated to a subagent.

This is an **input collector**, not an approval gate: it gathers the values the pipeline needs before it can run. There is no plan message, no Approve/Reject, and no pre-gate block here. State the context together with each question and read the answer. Never guess a value — if a required field is missing or vague, ask. Keep asking until every required dimension is complete and unambiguous.

The four required dimensions are `REQUIRED_BRIEF_DIMS`. The loop does not finish until all four pass the completeness check below.

## Required dimensions and their sub-fields

1. **offering**
   - `what` — what the user sells (product/service, in one or two sentences).
   - `value_prop` — the core value it delivers to a buyer.
   - `differentiators` — what sets it apart (1–3 points).
   - `proof_points` — evidence: case studies, results, named clients, metrics (or `none yet`).
1. **icp** (ideal customer profile)
   - `industries` — the target sectors (one or more). These become the climate combos.
   - `company_size` — employee or revenue band (or `any`).
   - `company_stage` — e.g., startup / growth / established / enterprise (or `any`).
   - `buyer_roles` — the decision-maker roles to reach (e.g., CTO, Head of Ops).
1. **geography**
   - `target_regions` — the regions/cities the prospects operate in (one or more). These pair with `industries` to form the climate combos.
   - `notes` — any geo nuance (language, in-region presence required, etc.) or `none`.
1. **goal_channels_voice**
   - `goal` — the desired outcome (e.g., booked discovery calls, demos, pilot deals).
   - `channels` — `email`, `linkedin`, or `both`.
   - `voice` — tone for later proposals (e.g., concise / consultative / formal).
   - `exclusions` — sectors, regions, or company types to avoid (or `none`).

Optional nice-to-have fields — capture only if the user volunteers them, never block on them: `budget`, `timeline`, `competitors`, `prior_outreach_results`.

## The loop

1. **Seed parse.** If `$ARGUMENTS` carried a seed, extract whatever dimensions it clearly specifies and pre-fill them. Mark everything else unknown. Do not infer a value the seed does not actually state.
1. **Find the gaps.** Determine which required sub-fields are still unknown or ambiguous. Order them by importance — `offering` and `icp` first, since they shape everything downstream.
1. **Ask.** Pose the open gaps to the user, batching related ones into a single `AskUserQuestion` call (up to four questions per call) using the fitting collector shape:
   - **Closed choice** for fixed sets (e.g., `channels`: email / linkedin / both; `voice`: concise / consultative / formal) — each value a named option.
   - **Confirm-or-customize** when sensible defaults exist (offer `Defaults` / `Minimal` style options; custom answers ride the free-text reply).
   - **Open value** for free-text answers (offering, value prop, industries) — ask a direct prose question stating what is needed and why; do not force a menu.
     State the context with each question. Never present a fenced block before the question.
1. **Re-assess.** After each answer round, re-check every required sub-field. Treat a vague answer ("enterprises mostly", "the usual channels") as still-ambiguous and ask a sharpening follow-up. Surface anything that seems off, internally inconsistent, or sub-optimal for the stated goal, and ask about it.
1. **Repeat** until the completeness check passes. There is no fixed number of rounds — continue until the brief is clear. If the user explicitly declines a sub-field, record it as `unspecified — user declined` and stop asking about that one.

## Completeness check

The loop is complete only when, for each of the four required dimensions, every sub-field is either filled with a concrete, unambiguous value or explicitly marked `unspecified — user declined`. In particular: `icp.industries` and `geography.target_regions` must each hold at least one concrete value, because their cross-product drives the climate research. If either is empty, the loop cannot end.

## Assemble the artifacts

When the check passes, write both files to the run directory.

`.mz/outreach/<run_name>/brief.json`:

```json
{
  "run_name": "<run_name>",
  "offering": { "what": "...", "value_prop": "...", "differentiators": ["..."], "proof_points": ["..."] },
  "icp": { "industries": ["..."], "company_size": "...", "company_stage": "...", "buyer_roles": ["..."] },
  "geography": { "target_regions": ["..."], "notes": "..." },
  "goal_channels_voice": { "goal": "...", "channels": "both", "voice": "...", "exclusions": ["..."] },
  "optional": { "budget": null, "timeline": null, "competitors": [], "prior_outreach_results": null }
}
```

`.mz/outreach/<run_name>/brief.md` — a human-readable rendering of the same content, one `##` section per dimension, used verbatim by the Phase 1.5 approval gate. Keep it faithful to `brief.json`; the gate shows this file.

## Close out

Update `.mz/task/<task_name>/state.md`: set `Phase` to `intake_complete`, refresh `what_remains`. Then proceed to **Phase 1.5: Brief Approval** (inline in `SKILL.md`). The clarification questions are captured automatically in the interaction journal by the `mz-memory` hook, so this phase logs nothing itself.
