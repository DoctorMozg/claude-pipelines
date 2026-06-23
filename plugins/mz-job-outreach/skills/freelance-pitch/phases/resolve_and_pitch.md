# Phases 0-4: Resolve gig, collect tone, generate proposal, review, write

## Phase 0: Resolve gig

Handled in SKILL.md's "Phase 0 entry" section. After resolution you have:

- `gig` — JSON record (from `latest_run/scored.json` or WebFetched off-pipeline).
- `run_dir` — where to write the proposal.
- `task_name` — for state.

If the gig came from `latest_run/scored.json`, the corresponding `latest_run/search_strategy.json` is the strategy file. If off-pipeline, there is no strategy file — the proposal-writer must operate without `rate_floor` (rate falls back to "to be discussed").

Write `<run_dir>/_pitch_temp/gig.json` with the resolved gig record for the proposal-writer to read.

```bash
mkdir -p <run_dir>/_pitch_temp
```

Write `.mz/task/<task_name>/state.md`:

```yaml
schema_version: 2
Status: running
Phase: 0
phase_complete: false
what_remains: []
Gig URL: <gig.url>
Gig title: <gig.title>
Run dir: <run_dir>
Off-pipeline: <true/false>
Strategy file: <path or null>
```

## Phase 1: Read CV + collect tone preference

Read the CV. If `latest_run/state.md` exists, look up the CV path from there. Otherwise AskUserQuestion to collect a fresh CV path (same validation as `/freelance-search` Phase 0).

Collect tone preference — a closed-choice input collector. Call `AskUserQuestion` once:

- question: `Choose how the proposal should read. The proposal-writer enforces a 350-word cap and grounding rules regardless; this only shifts voice.`
- options:
  - **Concise** — 200–280 words, terse sentences, no warm-up; best for vetted-network gigs where reviewers skim
  - **Conversational** — 280–340 words, warmer tone, allows contractions and one rhetorical line
  - **Formal** — 280–340 words, no contractions, full company names, signed off with full name

## Phase 1.5: Tone preference approval

The user's tone pick from Phase 1 IS the approval. No further gate needed at this step. Update `state.md` `Phase` to `tone_picked`.

## Phase 1.6: Reader-style read (inline)

Skipped when `personality:off` was passed; otherwise runs inline here (no subagent). This subtly calibrates the proposal to how the client reads, using the Social Styles model (Driver / Analytical / Amiable / Expressive). It is grounded-only, never names the trait, and never overrides the tone preference's sign-off or register (split by dimension).

1. **Role priorities (always).** From `gig.client_name_or_handle`, `gig.domain_or_industry`, and any role or title in the listing, note what this kind of buyer tends to prioritize (e.g. an agency lead leans to delivery and reliability; a founder to speed and outcomes; a procurement contact to price and risk). When nothing is inferable, stay neutral and mirror the listing's own register - a terse listing earns a terse proposal.
1. **Footprint (only when the client is named).** If `gig.client_name_or_handle` is a real name or handle (not "Undisclosed"), do a bounded public look-up (WebSearch/WebFetch, at most 3 calls) of their public professional signal - posts, bio, talks. If a citable cue supports a Social Style, record it with the cue; otherwise leave the style unset and keep role-priorities only. Professional signal only; never infer from photos or protected attributes.
1. **Compose the directive.** Write 2-4 imperative lines telling the writer the relative emphasis and length of the proposal's sections - based on the style when set, else on role-priorities. The directive shapes structure only: it never names the trait and never touches the salutation, sign-off, or voice register.

Store the result in `state.md` as `ReaderStyle` (the `social_style` or `role-priorities`, a `confidence`, and the `calibration_directive`). A thin or absent footprint yields a role-priorities or neutral directive - that is the expected common case for freelance gigs, not a failure. Update `state.md` `Phase` to `reader_style_read`.

## Phase 2: Generate proposal

Dispatch `freelance-proposal-writer`:

```
Write a freelance proposal for this gig.

Gig JSON path: <run_dir>/_pitch_temp/gig.json
CV path: <CV_PATH>
Strategy file path: <strategy_path or null if off-pipeline>
Tone preference: <Concise | Conversational | Formal>
Output file: <run_dir>/_pitch_temp/draft_v1.md

Word cap: 350. Strict.

Ground every milestone in a verbatim phrase from gig.project_scope_raw —
emit MILESTONE_UNGROUNDED: <text> for any milestone you cannot cite and
remove it.

Ground every pricing bracket in gig.budget_range_raw verbatim OR
strategy.rate_floor verbatim. If both absent, use "Rate to be discussed".

Apply the banned-phrase scan; rewrite any flagged sentence.

Open with a subject line and a salutation, close with a gratitude-leaning
sign-off, and use plain ASCII punctuation only - no em-dashes, en-dashes,
curly quotes, or ellipsis (write price ranges with a hyphen).

Reader calibration: <paste state.ReaderStyle.calibration_directive here, or
omit this whole line when personality:off or no directive was produced>. Apply
it to the relative emphasis and length of the proposal's sections, staying
inside the 350-word cap. It shapes structure only - never name or allude to the
client's inferred style, and never change the salutation, sign-off, or voice
register (those follow the tone preference).
```

Read `<run_dir>/_pitch_temp/draft_v1.md`. Capture word count, engagement type assumed, and any `MILESTONE_UNGROUNDED:` warnings the writer surfaced.

Update `state.md` `Phase` to `draft_v1_written`.

## Phase 3: Proposal review + edit loop

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<run_dir>/_pitch_temp/draft_v1.md` (or the current `draft_vN.md`) with the Read tool. Capture its full contents into context, along with the word count, tone, engagement type assumed, and any `MILESTONE_UNGROUNDED:` warnings surfaced by the writer. Grep the draft for AI-artifact punctuation (`grep -lP "[\x{2013}\x{2014}\x{2018}\x{2019}\x{201C}\x{201D}\x{2026}]" <run_dir>/_pitch_temp/draft_vN.md`); if any is present, re-dispatch the proposal-writer once with a fix instruction and overwrite the draft before emitting Surface 1.

**Surface 1 — emit the plan message.** Output the proposal draft verbatim as a normal markdown chat message. Emit the full verbatim contents of `<run_dir>/_pitch_temp/draft_vN.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Proposal ready for review — freelance-pitch

Drafted for <gig.title>. Word count: <N>. Tone: <tone>. Engagement type assumed: <engagement_type>.

<list any MILESTONE_UNGROUNDED warnings here, one per line, if present>

<verbatim contents of draft_vN.md>

---
**Approve** → write to <run_dir>/proposals/<gig_slug>.md and finish  ·  **Regenerate** → re-run the proposal-writer with the same inputs  ·  **Cancel** → drop the draft, nothing saved  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the proposal draft in the question body, it lives in the plan message above:

- question: `The proposal draft above is ready for review.`
- options:
  - **Approve** — write the proposal to `<run_dir>/proposals/<gig_slug>.md` and finish
  - **Regenerate** — re-run the proposal-writer with the same inputs (up to 2 total regenerates)
  - **Cancel** — drop the draft, no proposal saved

**Response handling**:

- **Approve** → proceed to Phase 4.
- **Regenerate** → if regenerate count < 2, re-dispatch proposal-writer with the same inputs, overwrite `draft_vN.md`, return to Surface 1, re-read and re-emit the full updated plan message, re-present the selector. If count == 2, call AskUserQuestion: "Two regenerates exhausted. Approve current draft, provide feedback, or Cancel?"
- **Cancel** → update `state.md` `Status` to `aborted_by_user`, drop `_pitch_temp`, stop.
- **Any other reply (feedback)** → re-dispatch proposal-writer with `Additional feedback: <text>` appended to the dispatch prompt, overwrite `draft_vN.md`, return to Surface 1, re-read and re-emit the full updated plan message, re-present the selector. This is a loop — repeat until the user explicitly approves or cancels.

## Phase 4: Write final proposal file

Slug the gig title: lowercase, strip non-alphanumeric except `-`, max 40 chars. Append a short URL hash if collision.

```bash
gig_slug=$(echo "<gig.title>" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/--*/-/g; s/^-//; s/-$//' | cut -c1-40)
cp "<run_dir>/_pitch_temp/draft_vN.md" "<run_dir>/proposals/${gig_slug}.md"
rm -rf "<run_dir>/_pitch_temp"
```

Update `state.md` — set `Status` to `complete`, `Phase` to `proposal_written`, `phase_complete` to `true`, `what_remains` to `[]`, and add:

```yaml
Final proposal: <run_dir>/proposals/<gig_slug>.md
Word count: <N>
```

Emit verification block per SKILL.md `Verification` section:

```
**Freelance proposal complete**

- Gig: <gig.title> — <gig.client_name_or_handle>
- Source: <gig.source>
- URL: <gig.url>
- Tone: <tone>
- Engagement type: <engagement_type>
- Word count: <N>
- Proposal file: <abs path>

Opener excerpt: > <first line of proposal body>
```
