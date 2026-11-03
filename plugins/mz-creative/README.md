<p align="center"><img src="https://raw.githubusercontent.com/DoctorMozg/claude-pipelines/master/assets/hero/mz-creative.webp" alt="mz-creative: expert panels &amp; writing" width="100%"></p>

# mz-creative

mz-creative adds five skills and 22 agents to Claude Code. Two run a panel of thinkers over your idea: `/brainstorm` generates options and `/expert` critiques a proposal. Three write: `/document` for technical docs, `/copywrite` for promotional copy, and `/naturalize` for text that reads like AI wrote it. It's for developers, founders and writers who want an idea pressure-tested from several angles, or docs and copy grounded in their own repo.

**Works in:** Claude Code and Cowork. All five skills dispatch agents, and claude.ai chat loads skills without their agents, so the pipelines don't run there.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-creative
```

Installing `mz-creative` also installs [mz-base](https://github.com/DoctorMozg/claude-pipelines/tree/master/plugins/mz-base), its dependency.

## Skills

### `/brainstorm`: Multi-Lens Ideation Panel

Picks 5 of the 16 lenses for you to approve. They then ideate in parallel, a panelist merges the ideas, and all five vote. It repeats for up to 5 rounds, stopping when one idea gets 3 votes. If none does, the report gives the top 2 or 3 with the vote split. Ideas are credited to their lens.

```
/brainstorm a pricing model for the new API tier
/brainstorm how to onboard non-technical admins to the dashboard
```

**Pipeline**: Panel selection, panel approval, parallel ideation, synthesis, voting rounds, then the report

### `/expert`: Delphi-Style Expert Consultation

Runs a fixed 3-round critique of one proposal by 5 lenses you approve first. Each panelist writes strengths, weaknesses, risks, suggestions, 1-5 scores and a confidence level. A neutral synthesizer summarizes each round, and panelists may change position after reading it. Every claim in the final report is tagged with its lens and round, such as `[lens-cto R2]`.

```
/expert review my proposed event-bus architecture in src/events/
/expert critique this RFC: <paste>
```

**Pipeline**: Intake, optional codebase scan, panel approval, 3 rounds (views, reactions, final positions), each followed by a synthesis, then the report

**Modifiers**: `scope:branch|global|working` has `expert-researcher` scan the repo first so critiques cite real code (default: none). `branch` is files changed on this branch, `working` uncommitted changes, `global` every file git doesn't ignore. `@doc:<path>` ingests an existing brief or RFC.

### `/document`: Technical Documentation Pipeline

Researches the codebase, drafts Diátaxis-aligned documentation (tutorial, how-to, reference, explanation, README, API), then runs the naturalize pass. Claims are grounded in real source, with no fabricated APIs. The result lands in `.mz/reports/`. A `@doc:` file you polish is left as it was.

```
/document write a README for the auth module
/document type:reference scope:branch the new webhook endpoints
/document @doc:docs/api.md polish the existing API reference
```

**Pipeline**: Codebase research, research approval, `expert-technical-writer` (opus), then auto-naturalize (sonnet)

**Modifiers**: `scope:branch|global|working` limits the research (default `global`). `type:tutorial|howto|reference|explanation|readme|api|all` (default `all`, the writer chooses). `@doc:<path>` polishes an existing document.

### `/naturalize`: AI-Text Rewriter

Rewrites AI-sounding text in one pass, with no approval gate. `expert-naturalizer` finds the patterns (vocabulary spikes, mechanical antithesis, low burstiness, fractal summaries, five-paragraph templates) and rewrites them. A script then checks the prose for banned punctuation (em and en dashes, semicolons, ellipsis characters, arrows). Given a file, it overwrites it in place, keeps the original under `.mz/task/`, and shows a diff. Pasted text comes back in chat. It assumes AI patterns are present, so don't use it to proofread human writing.

```
/naturalize <paste your text here>
/naturalize @file:docs/intro.md
/naturalize research:yes @file:blog_draft.md
/naturalize preserve:leverage,robust @file:docs/risk.md
```

**Pipeline**: optional web research, `expert-naturalizer` (sonnet), punctuation check (one fix-only retry), then in-place overwrite with a diff

**Modifiers**: `@file:<path>` (rewrite that file in place). `preserve:<terms>` (comma-separated terms kept verbatim). `research:yes` (pulls current 2025–2026 AI-pattern data for that run).

### `/copywrite`: Promotional Copywriting Pipeline

Researches positioning and the project's existing voice, drafts copy in the format you ask for, then runs the naturalize pass. It won't invent metrics or named customers: the brief you approve lists the evidence available, and gaps are flagged as open questions.

```
/copywrite format:landing for the new analytics tier
/copywrite format:announcement @brief:specs/v2_release.md
/copywrite format:email scope:branch launch email for the rate-limit feature
```

**Pipeline**: Positioning and codebase tone research, brief approval, `expert-copywriter` (opus), then auto-naturalize (sonnet)

**Modifiers**: `format:landing|email|announcement|social|changelog|pitch` (required, asked for if missing). `scope:branch|global|working` for tone-matching against the repo's existing copy (default `global`). `@brief:<path>` (strongly recommended).

## Lens roster

The 16 lens agents (all opus) serve both `/brainstorm` and `/expert`.

| Domain         | Lenses                                           |
| -------------- | ------------------------------------------------ |
| Engineering    | engineer, cto, devops, security                  |
| Product/Market | product, data, seo                               |
| Creative       | artist, storyteller                              |
| Theoretical    | mathematician, scientist, philosopher, historian |
| Strategic      | economist, futurist                              |
| Human factors  | psychologist                                     |

## Support agents

| Agent                      | Model  | Role                                 |
| -------------------------- | ------ | ------------------------------------ |
| `expert-researcher`        | sonnet | Codebase research for `/expert`      |
| `expert-round-synthesizer` | sonnet | Summary between Delphi rounds        |
| `expert-report-writer`     | sonnet | Final `/expert` report               |
| `expert-technical-writer`  | opus   | Documentation for `/document`        |
| `expert-naturalizer`       | sonnet | AI-pattern rewriter                  |
| `expert-copywriter`        | opus   | Copy in the six `/copywrite` formats |

## Writing pipelines

`/document` and `/copywrite` share one shape. The naturalize pass is mandatory. If it blocks, you get the un-naturalized draft and a warning.

```
├─ Phase 1: Research
│     └─ codebase scope + tone match (plus competitive positioning for /copywrite)
├─ Phase 1.5: Approval gate
│     └─ research or brief shown in chat, then Approve / Reject
├─ Phase 2: Write
│     └─ expert-technical-writer | expert-copywriter (opus)
└─ Phase 3: Auto-naturalize (mandatory)
      └─ expert-naturalizer rewrites in place, preserves CTAs, code, proper names
```

Output locations:

```
.mz/task/<YYYY_MM_DD>_<skill>_<slug>/
├── state.md                                   every skill
├── panel.md, ideas_round_<N>*.md, history.md  brainstorm
├── intake.md, research.md, panel.md,
│   iter_<N>_<lens>.md, round_<N>_summary.md   expert (research.md only with scope:)
├── research.md                                document
├── brief.md                                   copywrite
└── input.md, output.md, web_research.md       naturalize (web_research.md only with research:yes)

.mz/reports/<YYYY_MM_DD>_<skill>_<slug>.md     final output of every skill
```

## Workflows

- **Brainstorm to copy**: `/brainstorm <positioning angles>`, then `/copywrite format:landing @brief:<brainstorm report>`.
- **Research or build to docs**: `/deep-research` (mz-research-pipe) or `/build` (mz-dev-pipe), then `/document type:reference`.

## Data and network

The plugin runs inside your Claude Code session and has no server of its own. As in any session, your prompts and the files Claude reads go to the model you use. Beyond that:

- **No hooks, no telemetry.** mz-creative ships no hooks or MCP servers, and nothing is sent to the author. Its one script, `scripts/forbidden-punctuation.sh`, is a local check that `/naturalize` runs on the rewrite. It prints `file:line: <name> <char>` per banned character in prose, skips code, URLs, quotes and preserved terms, and writes nothing.
- **Files and git.** Task state and working files go to `.mz/task/<task_name>/` and reports to `.mz/reports/`, both under the project root. `/document` and `/copywrite` put their output there rather than editing your files. `scope:` runs read-only git commands (`diff`, `ls-files`, `status`, `log`, `merge-base`), and the skills pre-approve no commit, fetch or push.
- **`/naturalize` overwrites your file.** With `@file:<path>`, it saves the original to `.mz/task/<task_name>/input.md`, overwrites the file without asking, and shows a diff. Pasted text changes no file.
- **Approval gates.** `/brainstorm`, `/expert`, `/document` and `/copywrite` stop once for Approve or Reject. Other replies are feedback, and a missing answer is never approval. Before the gate they only plan: panel selection, an optional `/expert` codebase scan, or codebase and positioning research. Panelists, drafting and the naturalize pass run after approval.
- **Web access uses Claude Code's WebSearch and WebFetch.** It happens in `/copywrite` research for `landing`, `pitch` and major `announcement` formats, before the brief gate. `/brainstorm` lenses may also look up data or precedent. `expert-researcher` uses it only with `scope:`, and `/naturalize research:yes` goes through mz-base's `pipeline-web-researcher`. The writers and `expert-naturalizer` have the tools, but `/document` and `/copywrite` don't ask for web use.

## Support

- Issues: <https://github.com/DoctorMozg/claude-pipelines/issues>
- Email: drmozg@gmail.com
- Privacy: [PRIVACY.md](https://github.com/DoctorMozg/claude-pipelines/blob/master/PRIVACY.md)

## License

MIT
