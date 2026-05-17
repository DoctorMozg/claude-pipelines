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

Collect tone preference. Pre-gate block:

```
**Tone preference for this proposal**
Choose how the proposal should read. The proposal-writer enforces a 350-word cap and grounding rules regardless; this only shifts voice.

- **Concise** — 200–280 words, terse sentences, no warm-up. Recommended for vetted-network gigs where reviewers skim.
- **Conversational** — 280–340 words, warmer tone, allows contractions and one rhetorical line.
- **Formal** — 280–340 words, no contractions, full company names, signed off with full name.
```

AskUserQuestion options (single-select): `Concise`, `Conversational`, `Formal`.

## Phase 1.5: Tone preference approval

The user's tone pick from Phase 1 IS the approval. No further gate needed at this step. Update `state.md` `Phase` to `tone_picked`.

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
```

Read `<run_dir>/_pitch_temp/draft_v1.md`. Capture word count, engagement type assumed, and any `MILESTONE_UNGROUNDED:` warnings the writer surfaced.

Update `state.md` `Phase` to `draft_v1_written`.

## Phase 3: Proposal review + edit loop

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. Interactive — must not be delegated.

Pre-gate block:

```
**Proposal draft ready for review**
A freelance proposal has been drafted for <gig.title>. Word count: <N>. Tone: <tone>. Engagement type assumed: <engagement_type>.

<list any MILESTONE_UNGROUNDED warnings here, one per line>

- **Approve** → write to <run_dir>/proposals/<gig_slug>.md and finish
- **Regenerate** → re-run the proposal-writer with the same inputs (up to 2 total regenerates)
- **Feedback** → re-run the proposal-writer with your feedback appended to the dispatch prompt
- **Cancel** → drop the draft, no proposal saved
```

AskUserQuestion body (verbatim draft inline):

````
Proposal draft for <gig.title>. Please review:

```markdown
<verbatim contents of draft_v1.md>
```

Type **Approve** to save, **Regenerate** to retry with the same prompt, type your feedback to retry with your changes, or **Cancel** to drop the draft.
````

Response handling:

- **"approve"** → proceed to Phase 4.
- **"regenerate"** → if regenerate count < 2, re-dispatch proposal-writer with the same inputs, overwrite `draft_vN.md`, loop back. If count == 2, AskUserQuestion: "Two regenerates exhausted. Approve current draft, provide feedback, or Cancel?"
- **Feedback (free text)** → re-dispatch proposal-writer with `Additional feedback: <text>` appended to the dispatch prompt. Loop back.
- **"cancel"** → update `state.md` `Status` to `aborted_by_user`, drop `_pitch_temp`, stop.

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
