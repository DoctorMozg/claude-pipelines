# Phase 1: Positioning + Codebase Research

The orchestrator runs this phase directly (no subagent). The goal is to ground the copywriter in real product details, real audience, real positioning, and the project's existing voice — so it cannot invent metrics, customers, or capabilities. Output: `.mz/task/<task_name>/brief.md`.

## 1.1 Resolve scope

Convert `scope:` modifier to a file list (used for tone-matching, not for code review):

- `scope:working` — files in `git status --porcelain`
- `scope:branch` — files in `git diff --name-only $(git merge-base HEAD master)..HEAD` (or `main` if `master` doesn't exist)
- `scope:global` — entire repo, respecting `.gitignore`

If the resolved list is empty, continue without codebase tone-matching and note `Codebase tone-match: unavailable` in the brief.

## 1.2 Read the source brief

If `@brief:<path>` was provided, read it in full. Capture:

- The product or feature being promoted
- Audience (named segments — never "everyone")
- Value claim (the single sentence the reader must walk away with)
- Evidence: named customers, real numbers, dates, behaviors
- Brand constraints: tone words, banned words, voice samples
- Format-specific constraints: word limits, character limits, CTA destinations

If no `@brief:` was provided, derive these from `$ARGUMENTS` and what the codebase reveals. Flag missing items explicitly in the brief — do not invent.

## 1.3 Codebase tone-match (when scope yields files)

Read existing copy in the repo to capture the project's voice:

- `README.md`, `README.rst` at root and in subdirs
- `CHANGELOG.md`, `RELEASE_NOTES.md`
- `docs/` directory if present
- Marketing-site directories (`marketing/`, `landing/`, `site/`, `web/`)
- Existing email templates, social-post templates, pitch decks

Sample 5–10 paragraphs. Capture:

- **Voice**: formal vs conversational, third-person vs second-person
- **Vocabulary**: signature words the project uses repeatedly (these are protected — do not strip them in naturalize)
- **Structure**: how the project frames features (problem-first, demo-first, benefit-first)
- **Tone words**: confidence vs hedging, technical vs marketing
- **CTA style**: imperative vs invitation, link text patterns

If the codebase has no copy to learn from, note `Codebase tone-match: no prior copy found` and proceed.

## 1.4 Public surface (when relevant to the format)

Some formats benefit from grounding in real API/CLI/feature surface:

- **Landing page** + **announcement** — list the actual features and behaviors users will see
- **Email** — name the user-visible change concretely
- **Pitch** — name the actual product capabilities and integrations
- **Changelog** — list real merged PRs, real bug IDs, real user-visible changes

Capture: feature name, what it does for the user (not what the code does internally), file or PR reference.

For **social** and **release-note** formats with a known PR list, scan `git log` for the relevant range and pull commit subjects.

## 1.5 Web research — competitive positioning

For `landing`, `pitch`, and major `announcement` formats, do light competitive research via WebFetch / WebSearch:

- Find 2–3 named competitors and their positioning headlines
- Identify the differentiator the brief claims (or that the project's behavior reveals)
- Note category-standard CTAs and hero-section patterns in the space
- Avoid: AI-generated marketing summaries, undated case studies, aggregator review sites

If the brief explicitly says "no competitive research" or `email`/`changelog`/`social` formats are requested, skip this step.

## 1.6 Audience refinement

For each named audience segment, capture:

- **Job title or role** — concrete, not "everyone"
- **Their problem** — the pain that motivates them to read this copy
- **What they already know** — assumed background (avoid explaining it)
- **What they need to act** — the concrete next step

A landing page may serve 2–3 audiences; a pitch serves 1; a social post serves 1. Reduce the segments to the right count for the format.

## 1.7 Format-specific constraints

Capture format-specific rules to pass to the copywriter:

- **landing**: hero claim ≤140 chars, 3–5 H2 proof sections, primary + secondary CTA, who-it's-for section, social-proof block
- **email**: subject ≤55 chars, opening states value claim, 2–3 short paragraphs, single imperative CTA, real-name sign-off
- **announcement**: title is the headline change, "What's new" + "Breaking changes" + "Upgrading" + "Why this matters" sections
- **social**: ≤280 chars (or platform limit), specific hook with number/name/unusual fact, single CTA
- **changelog**: Keep a Changelog format, one user-visible change per line, no marketing language
- **pitch**: Problem / Solution / Why now / Traction / Team / Ask — one line each

## 1.8 Tone calibration

Decide the tone register based on:

- Brand constraints from the brief
- Audience expectations (engineers vs executives vs end users)
- Format conventions (changelogs are terse; landing pages can be expressive)
- Project codebase voice (when available)

Capture three tone decisions:

- **Confidence level**: assertive / balanced / hedged
- **Formality**: formal / professional / conversational
- **Specificity bias**: numbers-heavy / behavior-heavy / abstract (numbers-heavy is the default unless the brief specifies otherwise)

## 1.9 Write `brief.md`

Write `.mz/task/<task_name>/brief.md` using this structure:

```markdown
# Brief — <one-line description, format: <format>>

## Format
<landing | email | announcement | social | changelog | pitch>

## Audience
- <segment 1>: <role>, <their problem>, <what they need to act>
- <segment 2>: ...

## Value claim
<single sentence — the one promise the reader must walk away with>

## Evidence
- Named customers: <list, or "none provided">
- Real numbers: <list with sources, or "none provided">
- Behaviors: <concrete capability list, grounded in code or brief>

## Brand constraints
- Tone words: <list, or "none">
- Banned words: <list, or "none">
- Voice samples: <links/paths, or "none">

## Format-specific constraints
- <constraint relevant to this format>
- ...

## Tone decisions
- Confidence: <assertive | balanced | hedged>
- Formality: <formal | professional | conversational>
- Specificity bias: <numbers-heavy | behavior-heavy | abstract>

## Codebase tone-match
- Source files: <list, or "unavailable">
- Voice observed: <one-line description, or "no prior copy found">
- Signature vocabulary: <words to preserve in naturalization>

## Competitive positioning (when applicable)
- Competitor 1: <name> — <positioning headline> — <source>
- Competitor 2: ...
- Differentiator the brief claims: <one sentence>

## Public surface (when applicable to format)
- <feature/capability> — <user-visible behavior> — <file or PR reference>
- ...

## Proposed copy outline
<2–4 sentences describing the structural approach: which claim opens, which proof points support it, what the CTA is, where named users go>

## Open questions / gaps
- <gap or unverified claim — flagged for the user>
- ...
```

Keep it tight. Aim for 100–200 lines.

## 1.10 Hand off to Phase 1.5

Update `state.md`: phase → `research_complete`, append `brief.md` to `FilesWritten`. Phase 1.5 (approval gate) runs next, defined inline in SKILL.md.
