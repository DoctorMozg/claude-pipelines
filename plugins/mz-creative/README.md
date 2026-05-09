# mz-creative

Multi-perspective AI panels and creative writing pipelines. Two intent families share the plugin: **panels** that run a roster of intellectual lenses across an idea (brainstorm or critique), and **writing pipelines** that produce documentation, naturalized prose, and promotional copy with built-in approval gates.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-creative
```

## Skills

### `/brainstorm` — Multi-Lens Ideation Panel

Selects 5 lenses, runs them through parallel ideation, synthesizes proposals, and converges via vote rounds.

```
/brainstorm a pricing model for the new API tier
/brainstorm how to onboard non-technical admins to the dashboard
```

**Pipeline**: Panel selection → parallel ideation → synthesis → voting rounds → consensus

______________________________________________________________________

### `/expert` — Delphi-Style Expert Consultation

Selects 5 lenses and runs a 3-round Delphi critique on a proposal — view → summary → react — with a dedicated report-writer for the final synthesis.

```
/expert review my proposed event-bus architecture in src/events/
/expert critique this RFC: <paste>
```

**Pipeline**: Panel selection → Round 1 (independent views) → synthesis → Round 2 (reactions) → synthesis → Round 3 (final positions) → report

______________________________________________________________________

### `/document` — Technical Documentation Pipeline

Researches the codebase, drafts Diátaxis-aligned documentation (tutorial, how-to, reference, explanation, README, API), then auto-runs the naturalize pass to remove AI patterns. Always grounds claims in real source — no fabricated APIs.

```
/document write a README for the auth module
/document type:reference scope:branch the new webhook endpoints
/document @doc:docs/api.md polish the existing API reference
```

**Pipeline**: Codebase research → user approval → expert-technical-writer (opus) → auto-naturalize (opus)

**Modifiers**: `scope:branch|global|working`, `type:tutorial|howto|reference|explanation|readme|api|all`, `@doc:<path>` for polish jobs.

______________________________________________________________________

### `/naturalize` — AI-Text Rewriter

Detects AI patterns (vocabulary spikes, mechanical antithesis, em-dash overuse, low burstiness, fractal summaries, five-paragraph templates), shows you the analysis, gets approval, then rewrites via the expert-naturalizer agent. Optional in-place file update gate when input came from a file.

```
/naturalize <paste your text here>
/naturalize @file:docs/intro.md
/naturalize research:yes @file:blog_draft.md
```

**Pipeline**: Pattern analysis (+ optional web research) → user approval → expert-naturalizer (opus) → optional in-place update gate

**Modifiers**: `@file:<path>` (lets you optionally overwrite the original after the rewrite), `research:yes` (refreshes the embedded vocabulary list against current 2025–2026 pattern data).

______________________________________________________________________

### `/copywrite` — Promotional Copywriting Pipeline

Researches positioning and the project's existing voice, drafts copy in the requested format (landing page, email, announcement, social, changelog, pitch one-pager), then auto-runs the naturalize pass. Will not invent metrics or named customers — every claim ties back to the brief.

```
/copywrite format:landing for the new analytics tier
/copywrite format:announcement @brief:specs/v2_release.md
/copywrite format:email scope:branch launch email for the rate-limit feature
```

**Pipeline**: Positioning + codebase tone research → brief approval → expert-copywriter (opus) → auto-naturalize (opus)

**Modifiers**: `format:landing|email|announcement|social|changelog|pitch` (required), `scope:branch|global|working`, `@brief:<path>` (strongly recommended).

## Lens Roster

The 16 lens agents are shared between `/brainstorm` and `/expert`. Each lens has a fixed intellectual personality; the dispatching skill injects whether it should ideate or critique.

| Domain         | Lenses                                           |
| -------------- | ------------------------------------------------ |
| Engineering    | engineer, cto, devops, security                  |
| Product/Market | product, data, seo                               |
| Creative       | artist, storyteller                              |
| Theoretical    | mathematician, scientist, philosopher, historian |
| Strategic      | economist, futurist                              |
| Human factors  | psychologist                                     |

## Support Agents

| Agent                      | Model  | Role                                                                                        |
| -------------------------- | ------ | ------------------------------------------------------------------------------------------- |
| `expert-researcher`        | opus   | Codebase scope research for `/expert`                                                       |
| `expert-round-synthesizer` | sonnet | Cross-lens summarization between Delphi rounds                                              |
| `expert-report-writer`     | opus   | Final consultation report after all 3 rounds                                                |
| `expert-technical-writer`  | opus   | Diátaxis-aligned documentation grounded in research artifacts                               |
| `expert-naturalizer`       | opus   | AI-pattern rewriter — vocabulary, rhythm, structural template breakage                      |
| `expert-copywriter`        | opus   | Promotional copy across landing / email / announcement / social / changelog / pitch formats |

22 agents total = 16 lens personas + 6 support agents.

## Pipeline Pattern

The three writing pipelines share a phase pattern. Every output goes through naturalize — there is no "skip the polish" knob:

```
/document or /copywrite
  │
  ├─ Phase 1: Research
  │     └─ codebase scope + tone match (or positioning + competitive research)
  ├─ Phase 1.5: Approval gate (verbatim research/brief in AskUserQuestion)
  ├─ Phase 2: Write
  │     └─ expert-technical-writer | expert-copywriter (opus)
  └─ Phase 3: Auto-naturalize (mandatory)
        └─ expert-naturalizer rewrites in place, preserves CTAs/code/proper names
```

`/naturalize` runs the same naturalizer agent in standalone mode, with an additional in-place file update gate when the input came from `@file:<path>`.

## Output locations

```
.mz/task/<YYYY_MM_DD>_<skill>_<slug>/
├── state.md
├── research.md  | brief.md  | analysis.md
└── input.md     (naturalize only)

.mz/reports/<YYYY_MM_DD>_<skill>_<slug>.md
```

## Workflows

A few sensible chains across this plugin and the rest of the marketplace:

- **Research → docs**: `/deep-research` (mz-dev-pipe) → `/document type:reference` — survey the field, then write the reference doc grounded in research findings.
- **Brainstorm → copy**: `/brainstorm <positioning angles>` → `/copywrite format:landing` — explore positioning ideas across lenses, then write the landing page from the winning angle.
- **De-AI a draft**: `/naturalize @file:draft.md` — standalone clean-up of any AI-generated prose, with an optional in-place overwrite gate.
- **Build a feature with documentation**: `/build` (mz-dev-pipe) → `/document type:reference` — ship the feature, then auto-document it.

## License

MIT
