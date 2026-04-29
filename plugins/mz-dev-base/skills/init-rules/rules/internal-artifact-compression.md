## Compressed Style for Internal Artifacts

Pipeline agents and orchestrators produce a lot of intermediate text that other agents read and humans rarely do. Default to compressed prose for those artifacts — token savings compound across review loops, lens panels, and synthesizer chains. Keep human-readable style for everything humans actually read.

## Apply To (default ON)

Internal-only artifacts:

- `.mz/task/<name>/state.md` — orchestrator phase tracking
- `.mz/task/<name>/research.md` — when only agents consume it
- Lens panelist raw outputs (brainstorm/expert rounds 1, 2, 3)
- Round-synthesizer outputs in `/expert`
- Code-reviewer summaries fed back to coders
- Test-reviewer outputs fed to orchestrators
- Dispatch briefs sent to subagents

## Never Apply To (exemption list)

User-facing prose stays human-readable:

- Final reports under `.mz/reports/` and `.mz/reviews/`
- `plan.md` shown verbatim in approval gates
- README files, guideline documents, agent and skill definition files
- Code comments, commit messages, PR descriptions
- Documentation files (technical docs, user guides, API references)

Output of text-craft agents — these agents exist to produce human prose, so their outputs must never be compressed:

- `expert-naturalizer` — adds burstiness; compression is the opposite operation
- `expert-technical-writer` — produces docs humans read
- `expert-copywriter` — produces marketing prose humans read
- `expert-report-writer` — produces final user-facing reports

When unsure whether an artifact is internal or user-facing, default to human-readable.

## Preserve Verbatim

Regardless of mode, never touch:

- Code blocks and inline code
- URLs, file paths, command lines, flags, environment variables
- Frontmatter (YAML), JSON, structured data
- Version strings, dates, proper nouns, technical terms
- Headings, list markers, table structure

If a line contains a path, command, or version, leave the surrounding prose alone too.

## Compression Rules

When compression is ON:

- Drop articles (a/an/the) where meaning is preserved
- Drop hedging (just/really/basically/somewhat/actually)
- Drop pleasantries and connective fluff
- Use fragments where complete sentences are unnecessary
- Use arrows (`X -> Y`) for transitions and causation

Compression preserves substance and structure. It does not invent abbreviations, drop context the next agent needs, or compress at the cost of correctness.

## Why

Pipeline skills produce a lot of intermediate text. `/expert` runs 5 lenses across 3 rounds (15 raw outputs + 3 synthesis passes). `/build` runs reviewers up to 3 times per phase. Most of that text is read once by an agent and discarded. Compressing internal traffic preserves budget for the surfaces humans actually read — final reports, plans presented in approval gates, written documentation, copy.
