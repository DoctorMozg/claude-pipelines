---
name: freelance-pitch
description: ALWAYS invoke when the user wants to draft a freelance proposal for a single gig — by rank from /freelance-search, by URL, or picked from a list. Triggers: "freelance pitch", "draft proposal", "pitch this gig", "proposal for gig 3".
argument-hint: "[<rank-N> | <gig-URL>] [personality:off]"
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Freelance Pitch

## Overview

You generate a single grounded freelance proposal for a selected gig. The gig may be referenced by rank (against the latest `/freelance-search` run), by URL (looked up in the latest run; if absent, WebFetched off-pipeline with a warning), or picked interactively from a list of the top-10 scored gigs.

The proposal is a markdown file at `.mz/outreach/<run_dir>/proposals/<gig_slug>.md`. Word cap: 350. Hard. Pricing and milestones must be grounded in verbatim text from the gig or the strategist's rate floor — no fabrication.

## When to Use

Invoke when the user wants to draft a proposal for one specific freelance gig. Trigger phrases: "draft a proposal", "pitch this gig", "freelance pitch", "proposal for gig <N>", "proposal for <URL>".

### When NOT to use

- The user wants to find gigs — use `/freelance-search` instead.
- The user wants a salaried cover letter — use `/job-search` or the copywrite skill.
- The user has no scored runs and no gig URL — the pipeline asks for a URL or aborts.

## Input

- `$ARGUMENTS` — optional, one of:
  - An integer rank (e.g. `3`) → resolve against the latest `<RUN_DIR>/scored.json`.
  - A URL → look up in the latest `scored.json`; if not found, WebFetch with a warning.
  - Empty → interactive picker.

## Directory Structure

- **State** — `.mz/task/<task_name>/state.md`.
- **Output** — when resolving against an existing freelance-search run: `.mz/outreach/<freelance-search-run-dir>/proposals/<gig_slug>.md`. When operating off-pipeline (URL with no prior run): `.mz/outreach/<YYYY_MM_DD>_freelance_pitch_<slug>/proposals/<gig_slug>.md`.

## Core Process

### Phase Overview

| #   | Phase                         | Agent(s)                          | Details                       |
| --- | ----------------------------- | --------------------------------- | ----------------------------- |
| 0   | Resolve gig (rank/URL/picker) | — (orchestrator, AskUserQuestion) | `phases/resolve_and_pitch.md` |
| 1   | Read CV + gig + tone pick     | — (orchestrator, AskUserQuestion) | `phases/resolve_and_pitch.md` |
| 1.5 | Tone preference approval      | — (orchestrator)                  | `phases/resolve_and_pitch.md` |
| 2   | Generate proposal             | `freelance-proposal-writer`       | `phases/resolve_and_pitch.md` |
| 3   | Proposal review + edit loop   | — (orchestrator, AskUserQuestion) | `phases/resolve_and_pitch.md` |
| 4   | Write final proposal file     | — (orchestrator)                  | `phases/resolve_and_pitch.md` |

Read the phase file when reaching Phase 0.

## Techniques

Delegated to phase file.

## Common Rationalizations

N/A — orchestration skill.

## Red Flags

- You generated a proposal without a CV — proposal-writer cannot ground the credibility hook.
- You allowed a milestone with no verbatim grounding from `gig.project_scope_raw`.
- You let a pricing figure stand that does not trace to `gig.budget_range_raw` or `strategy.rate_floor`.
- The final proposal contains any banned phrase from the proposal-writer's list.
- The proposal exceeds 350 words.
- You skipped the user approval gate at Phase 3.

## Verification

Before completing, output a visible block showing: gig title, gig URL, source, output file path, word count, engagement type assumed, and a one-line excerpt of the opener. Confirm the proposal file exists on disk.

______________________________________________________________________

## Phase 0 entry

Parse `$ARGUMENTS`:

- Integer (e.g. `3`) → `rank_arg`.
- URL (starts with `http://` or `https://`) → `url_arg`.
- `personality:off` token (anywhere in `$ARGUMENTS`) → `personality_mode = off` (default `on`); disables the Phase 1.6 reader-style read so proposals use neutral structure.
- Empty (no rank or URL) → interactive picker.

Discover the most recent freelance-search run:

```bash
latest_run=$(ls -dt .mz/outreach/*freelance_search_* 2>/dev/null | head -n 1)
```

Branching:

- **`rank_arg` set** → require `latest_run`. If absent, AskUserQuestion: "No prior /freelance-search run found. Provide a gig URL, or **Cancel**."
- **`url_arg` set** → if `latest_run` exists, look up the URL in `latest_run/scored.json`. If found, use the scored record. If not found, WebFetch the URL and treat as off-pipeline (warn: no prior scoring).
- **Empty** → if `latest_run` exists, AskUserQuestion with a single-select menu of the top-10 scored gigs (label = `#<rank> <title> — <client> (score <score>)`) plus an "Other URL" option. If no `latest_run`, AskUserQuestion demands a URL or aborts.

Set `task_name = <YYYY_MM_DD>_freelance_pitch_<gig_slug>`. Set `run_dir`:

- If gig came from `latest_run`'s `scored.json`: `run_dir = latest_run` (proposals nested under existing run).
- If gig is off-pipeline (URL with no prior scoring): `run_dir = .mz/outreach/<task_name>` (new sibling directory).

```bash
mkdir -p .mz/task/<task_name>
mkdir -p <run_dir>/proposals
```

Read `phases/resolve_and_pitch.md` for the rest.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

## Error Handling

- Off-pipeline WebFetch fails: AskUserQuestion to retry the URL or Cancel.
- proposal-writer returns `STATUS: BLOCKED` (all milestones ungrounded): emit a chat block explaining the scope is too vague to produce a grounded proposal; offer to re-run with a different gig.
- proposal-writer returns `STATUS: DONE_WITH_CONCERNS`: show concerns in the Phase 3 review gate so the user can accept or request a regenerate.

## Resume Support

Phase 0 always re-resolves the gig (cheap). Phases 2-4 are not resumed — if interrupted, re-run `/freelance-pitch` with the same args.
