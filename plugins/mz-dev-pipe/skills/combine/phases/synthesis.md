# Phase 3: Cross-Reference Synthesis (and Phase 5: Report)

This phase file covers three orchestrator responsibilities: cross-reference synthesis of the parallel lens extracts (Phase 3), the conditional gap-fill approval gate body (Phase 3.5), and task-adaptive final report generation (Phase 5). Read the section that matches your current phase — do not read the whole file upfront.

## Contents

- Phase 3: Cross-Reference Synthesis — 3.1 read extracts, 3.2 cross-reference, 3.3 emergent patterns, 3.4 gap consolidation.
- Phase 3 → 3.5 Handoff — short-circuit when residual gaps are empty.
- Phase 3.5 Gate — full Rule-1 gate body (presentation, prompt, handling, loop language, orchestrator-only notice).
- Phase 5: Task-Adaptive Report Generation — 5.1 section derivation, 5.2 meta-sections, 5.3 report template, 5.4 collision handling, 5.5 state update.
- Phase 5 → User — 5-line summary.

______________________________________________________________________

## Phase 3: Cross-Reference Synthesis

Entry: Phase 2 finished and every approved lens wrote an `extract_<lens>.md` under `.mz/task/<task_name>/`. Any `BLOCKED` lens was already escalated in `phases/lens_dispatch.md §Phase 2.3`; do not begin Phase 3 until the outstanding `BLOCKED` / `NEEDS_CONTEXT` cases are resolved.

### Phase 3.1: Read every lens extract

1. List the task directory: `ls .mz/task/<task_name>/extract_*.md`.
1. For each file in that list, read it top-to-bottom. Capture: the `## Summary`, every row of `## Extracts` (fact, source path, confidence), every `## Conflicts` entry, every `## Gaps` entry, and the `## Files read` list.
1. Maintain an in-memory index per extract with: lens name, summary sentences, extracts list, conflicts list, gaps list, files read.
1. If any `extract_<lens>.md` is missing despite the lens being marked returned in `state.md`, log a warning, mark the lens as degraded for synthesis purposes, and continue — do not re-dispatch from this phase (re-dispatch is Phase 2.3's responsibility).

### Phase 3.2: Cross-reference step

Walk the aggregated extracts and classify every claim by how many lenses surface it:

- **Corroborated (confidence: high)** — the same claim (semantically, not just lexically) appears in 2 or more lenses. Normalize by stripping leading/trailing whitespace, lowercasing, and collapsing internal whitespace before comparing; additionally treat two claims as matching if one is a strict substring of the other and the shorter is ≥ 30 characters. Record the set of contributing lenses and every source file/line cited by any of them.
- **Single-source (confidence: as-reported)** — the claim appears in exactly 1 lens. Carry forward the lens-reported confidence (`high` / `medium` / `low`) unchanged — do not silently upgrade it.
- **Conflict (confidence: low)** — the claim is flagged with a `CONFLICT DETECTED` token in any extract, or two lenses make claims that directly contradict each other on the same entity (e.g., one extract says `retry_limit = 3`, another says `retry_limit = 5`). Every conflict entry must preserve both sides and the source file for each side. The literal string `CONFLICT DETECTED` must appear in `synthesis.md` under `## Conflicts` for every conflict surfaced, matching the token emitted by the lens agents in `phases/lens_dispatch.md §Phase 2.2`.

Do not drop any claim during cross-reference. Low-confidence and conflicting claims stay — they are signal, not noise.

### Phase 3.3: Emergent-pattern detection

After classifying, scan the aggregated extracts a second time looking for patterns that span 2 or more lenses but that no individual extract named:

- Recurring file paths referenced across lenses (even if the claims differ).
- Shared vocabulary (a technical term appearing in ≥ 3 lenses suggests a cross-cutting theme).
- Chronological clustering (several extracts dated within the same week suggest a related initiative).
- Common root causes (multiple single-source findings that share a failure mode).

Record each emergent pattern as: pattern name, contributing lenses, one-sentence description, confidence (medium by default — emergent patterns are inference, not corroboration).

### Phase 3.4: Gap consolidation

1. Collect every `GAP:` token from every extract's `## Gaps` section into a flat list, preserving each entry's originating lens.
1. Normalize each gap text by trimming outer whitespace, collapsing internal whitespace runs, and lowercasing.
1. Deduplicate on the normalized text. When the same gap surfaces from multiple lenses, keep one entry and record all contributing lenses.
1. The deduplicated list is the **residual gap list**. This list feeds Phase 3.5.

### Phase 3 artifact write

Write `.mz/task/<task_name>/synthesis.md` with these sections in order:

- `## Corroborated findings` — one bullet per corroborated claim: claim text, contributing lenses, source file list, **Confidence: high**.
- `## Single-source findings` — one bullet per single-source claim: claim text, originating lens, source file, lens-reported confidence.
- `## Conflicts` — one bullet per conflict: both sides with source files, literal `CONFLICT DETECTED:` prefix, **Confidence: low**.
- `## Emergent patterns` — one bullet per pattern from 3.3.
- `## Residual gaps` — numbered list from 3.4 (one line per gap, with contributing lenses in parentheses). If empty, the section body is the literal string `none`.
- `## Lens coverage` — a table: lens name, extract path, extracts count, conflicts count, gaps count, status (`ok` / `degraded`).

After writing, update `state.md` phase to `synthesized` and record synthesis artifact path, corroborated count, single-source count, conflict count, residual gap count.

______________________________________________________________________

## Phase 3 → 3.5 Handoff

Inspect the residual gap list produced by Phase 3.4:

- **If the residual gap list is empty** → skip Phase 3.5 entirely and proceed directly to Phase 5 (continue reading this file at `## Phase 5: Task-Adaptive Report Generation`). Record `gap_fill: skipped_empty` in `state.md`.
- **Otherwise** → return control to `SKILL.md §Phase 3.5: Gap-Fill Approval Gate (conditional)`. That stub will read `§Phase 3.5 Gate` below for the full presentation content, prompt body, handling, and loop language, then issue the `AskUserQuestion` call itself. Do not issue the `AskUserQuestion` call from this file — the orchestrator handles it at the SKILL.md stub.

______________________________________________________________________

## Phase 3.5 Gate

**Skip-if-empty reminder**: If the residual gap list produced by Phase 3 is empty, skip this gate entirely and proceed directly to Phase 5. (The SKILL.md stub already short-circuits this case, but repeat here in case this file is opened directly.)

### Presentation content

Before issuing the `AskUserQuestion` call, compose a residual gap summary block containing:

1. **Total residual gap count** — integer from the deduplicated list in Phase 3.4.
1. **Per-gap lines** — one line per gap with three fields:
   - The gap text (exactly as normalized in 3.4).
   - The contributing lens(es) that surfaced it (e.g., `surfaced by: research, codebase`).
   - A short reason the local sources could not resolve it (e.g., `local sources predate the refactor`, `no vendor documentation on disk`, `only covered at a high level, no version-specific detail`). If no reason is derivable, use `local sources did not cover this topic`.
1. **Cost estimate** — the number of web `pipeline-web-researcher` (opus) agents that would be dispatched if approved. Cap the count at `MAX_LENSES` (6 by §7 constants) in a single wave; if the gap list exceeds 6, state that the smallest-scope gaps will be merged until the wave fits under the cap, and reference `phases/lens_dispatch.md §Phase 4` for the exact merge rules.

### Verbatim AskUserQuestion prompt body template

The orchestrator issues an `AskUserQuestion` call from `SKILL.md §Phase 3.5` using this exact message body (fill the `<…>` placeholders with the content from the presentation block above):

```
Residual gaps after local synthesis:

<numbered gap list with source lens and reason>

Dispatch web gap-fill? (up to MAX_LENSES pipeline-web-researcher agents, single wave)

Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.
```

### Response handling

- **"approve"** → update `state.md` phase to `gapfill_approved`, then proceed to Phase 4 by reading `phases/lens_dispatch.md §Phase 4: Web Gap-Fill (conditional)`. Record the approved gap list in `state.md` verbatim so Phase 4 can dispatch against it.
- **"reject"** → update `state.md` phase to `gapfill_declined`, skip Phase 4 entirely, and proceed directly to Phase 5 with the residual gaps marked unresolved in the final report's `## Gaps ### Unresolved` section.
- **Feedback** → incorporate the feedback without re-running Phases 1–3. Feedback may: drop gaps from the list, merge two gaps into one (update the normalized text), rewrite a gap's text for clarity, or add a reason the user knows but the synthesis missed. Re-present the revised list **via AskUserQuestion** using the same message body template above.

### Loop language

This is a loop — repeat until the user explicitly approves or rejects. Never dispatch web researchers without explicit approval.

### Orchestrator-only notice

This gate body is read by the orchestrator directly. It must NEVER be delegated to a subagent. The orchestrator reads this section, then issues the `AskUserQuestion` call itself from SKILL.md §Phase 3.5.

______________________________________________________________________

## Phase 5: Task-Adaptive Report Generation

Entry: either Phase 3 produced an empty residual gap list (skipped 3.5 and 4), or Phase 3.5 was rejected (skipped 4), or Phase 4 completed and wrote its `gapfill_<id>.md` files under `.mz/task/<task_name>/`.

Read `state.md` to recover: task text, task slug, output path override (if any), `sections:` parameter (if any), lens list, lens coverage table from `synthesis.md`, residual gap list, gap-fill resolution outcomes.

### Phase 5.1: Section derivation — branch on the `sections:` parameter

The top-level report sections come from one of two sources, chosen by whether the user supplied the `sections:` parameter at invocation time.

**If `sections:` was supplied** (found in `state.md` under the `Sections` field, set by Phase 0.1):

1. Parse the comma-separated list from `state.md`. Trim whitespace from each entry. Preserve the order exactly as the user supplied it.
1. Use each entry verbatim as a top-level report section heading. Do not rename, merge, or re-order.
1. Skip noun-phrase derivation entirely.
1. Log `sections_source: user-supplied` in `state.md`.
1. If synthesis content does not map cleanly into one of the user-supplied sections, keep that section header in the report with the body `See Executive Summary` — do not silently drop it and do not silently re-derive additional sections.

**If `sections:` was NOT supplied**, derive report sections from the task text. This is `/combine`'s task-adaptive behavior and has no in-repo precedent:

1. Tokenize the task text on whitespace. Lowercase the tokens. Remove stopwords (`the`, `a`, `and`, `or`, `of`, `to`, `in`, `on`, `for`, `with`, `our`, `we`, `i`, `about`, `from`, `that`, `this`, `what`, `how`, `why`, `when`).
1. Extract noun phrases. A noun phrase is any 1–3 contiguous token run that does not contain a stopword and that names a concrete artifact, component, or concept (e.g., `auth refactor`, `websocket reconnection logic`, `caching layer invalidation`, `rate limiter`). If the task text is short, single-token phrases are acceptable.
1. For each extracted noun phrase, count how often it appears across all `extract_<lens>.md` files aggregated in Phase 3. Order the noun phrases by this count descending — most-covered first.
1. Create one top-level section per noun phrase, named after the noun phrase (title-cased). Sections appear in the order determined by step 3.
1. **Broad-task fallback** — if the task text is too broad to extract at least 2 distinct noun phrases (e.g., `summarize everything`, `tell me what we know`, or the extraction yields only stopwords after filtering), fall back to creating one section per lens name from the lens coverage table in `synthesis.md`, in the order the lenses were dispatched.
1. Log `sections_source: task-derived` in `state.md`.

In both branches, the derivation rule is: **derive report sections from the task** (or from the user override), not from a fixed template. The synthesis content is then routed into whichever section best matches each claim by its subject matter.

### Phase 5.2: Always-appended meta-sections

Regardless of whether 5.1 took the user-supplied or task-derived branch, append these meta-sections to the report after the task-adaptive sections, in this order.

**Collision rule**: if the user supplied a `sections:` value containing a name that case-insensitively matches one of the meta-section headers below (most commonly `Sources`, `Gaps`, `Timeline`, `Conflicts`, `Methodology`), **skip the meta-section with the colliding name** — the user-supplied section has already reserved that slot in the task-adaptive block and will be written once. Do not emit a second header under the same name. Log the skipped meta-section names in `state.md` under `meta_sections_skipped: <list>`.

- `## Timeline` — include only if the `git_history` lens ran (check the lens coverage table in `synthesis.md`). Content: chronological condensation of dated events from the extracts, grouped by week or month depending on span.
- `## Conflicts` — include always. Body: every `CONFLICT DETECTED` entry from `synthesis.md §Conflicts`, with both sides cited by source file. If there are no conflicts, the body is the literal string `None.`
- `## Gaps` — include always, with two sub-sections:
  - `### Resolved via web gap-fill` — one bullet per gap that was filled in Phase 4 (reference `.mz/task/<task_name>/gapfill_<id>.md` by path; cite the answer with its source URL and confidence from the gap-fill agent's output). If Phase 4 did not run, this sub-section body is the literal string `None.`
  - `### Unresolved` — one bullet per gap from the residual gap list that was not resolved (either because Phase 3.5 was rejected, or because Phase 4 returned `UNVERIFIED` for that gap). Include the reason. If none, body is the literal string `None.`
- `## Sources` — deduplicated list of every local file and every web URL cited in the report. Split into `### Local files` (with age in days and owning lens) and `### Web (from gap-fills, if any)` (with publication date and confidence). If no web gap-fills ran, the web sub-section body is `None.`
- `## Methodology` — five bullets: lenses dispatched (names), gap-fill wave (yes/no, count), approval gates passed (Phase 1.5 timestamp, Phase 3.5 timestamp or `n/a`), sections source (`task-derived` or `user-supplied`), synthesis artifact path.

### Phase 5.3: Write the report

Use the `output:` override from `state.md` if present; otherwise use the default path `.mz/reports/combine_<YYYY_MM_DD>_<slug>.md` where `<YYYY_MM_DD>` is today's date and `<slug>` is the snake_case task slug from Phase 0.3.

Write the report using this template (fill placeholders; adapt the task-adaptive section list to the result of 5.1; keep the meta-section headers exactly as written):

```markdown
# Combined Report: <task summary>

**Date**: <YYYY-MM-DD>
**Task**: <full task text>
**Lenses run**: <N> (<names>)
**Local sources consulted**: <N>
**Web gap-fills**: <N or "none">
**Sections source**: <task-derived | user-supplied>

## Executive Summary

3-5 paragraphs covering the most important corroborated findings, the most surprising contradictions, and the biggest residual gaps. Written so a reader can stop here and still have the top-level answer.

## <Section 1 — task-derived or user-supplied>

### Corroborated
- Finding — [source1](path), [source2](path). **Confidence: high**

### Single-source
- Finding — [source](path). **Confidence: medium**

### Conflicts (if any in this section)
- CONFLICT: <source A> says X, <source B> says Y.

## <Section 2>

...

## Timeline

(only if the `git_history` lens ran; chronological condensation from the extracts)

## Conflicts

Every CONFLICT DETECTED token from the lens extracts, with both sides cited.

## Gaps

### Resolved via web gap-fill
- <gap> — answer from `gapfill_<id>.md` with source URL and confidence.

### Unresolved
- <gap> — reason it was not resolved.

## Sources

### Local files
- path (age: X days, lens: <lens>)

### Web (from gap-fills, if any)
- URL (publication date, confidence)

## Methodology
- Lenses dispatched: <list>
- Gap-fill wave: <yes/no, gap count>
- Approval gates passed: Phase 1.5 <timestamp>, Phase 3.5 <timestamp or n/a>
- Sections source: <task-derived | user-supplied>
- Synthesis artifact: `.mz/task/<task_name>/synthesis.md`
```

### Phase 5.4: Collision handling

Before writing, check whether the resolved report path already exists on disk. If it does:

1. Append `_v2` to the basename (before `.md`).
1. If that also exists, try `_v3`, `_v4`, … until a free slot is found.
1. Log the final path (including any version suffix) in `state.md` under `Output`.

This matches Rule 11 in `SKILL_GUIDELINES.md`. Do not overwrite an existing report under any circumstances.

### Phase 5.5: Update state

After the report file is written, update `state.md`:

- `Status` → `completed`
- `Phase` → `report_written`
- `Output` → absolute path of the report just written
- `Sections source` → `task-derived` or `user-supplied`
- `Completed` → current timestamp

______________________________________________________________________

## Phase 5 → User

Present a 5-line summary to the user. This satisfies the `## Verification` block in `SKILL.md`:

1. `Report: <absolute path>` — from `state.md §Output`.
1. `Lenses: <N> (<comma-separated lens names>)` — from the lens coverage table.
1. `Local sources: <N>` — total distinct source files cited in the report.
1. `Gap-fills: <N or "none">` — number of gaps resolved in Phase 4, or `none` if Phase 4 did not run.
1. `Top findings: <1>; <2>; <3>` — the three most important corroborated findings from the Executive Summary, each condensed to one clause.

Confirm the report file exists on disk (`ls <path>`) before printing the summary. If the file is missing despite step 5.3 reporting success, surface the failure to the user with the state file path so they can inspect — do not silently retry.
