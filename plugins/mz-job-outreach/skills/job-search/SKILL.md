---
name: job-search
description: ALWAYS invoke when the user wants to find vacancies, match jobs against a CV, or build a job-hunt shortlist with cover letters. Triggers: "find me a job", "search jobs", "match vacancies to my CV", "job hunt", "find openings".
argument-hint: "<free-text preferences>" [limit:N] [recency:Nd] [contacts:topN] [letters:topN]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Job Search Pipeline

## Overview

You are an orchestrator that drives a full job-hunt intelligence pipeline. Given a candidate CV (markdown/plain text) and a free-text preferences prompt, you define a search strategy, gather sources, scout multiple job boards in parallel, normalize and filter listings against location eligibility and recency, score each vacancy against the CV on a weighted multi-axis model, find recruiter contacts for the top matches, generate per-vacancy cover letters, and produce a single ranked executive report.

Output is a single master markdown report (not per-vacancy dossier cards). Cover letters are written as side artifacts under `letters/<job_slug>.md`, ready to copy-paste into applications.

## When to Use

Invoke when the user wants to discover open roles matching their CV, build a job shortlist, or prepare for outreach to recruiters. Trigger phrases: "find me a job", "match vacancies to my CV", "job hunt", "search openings", "find roles".

### When NOT to use

- The user wants to draft a single cover letter for a specific known role — that is a copywriting task, use the copywrite skill.
- The user wants to revise their CV — this skill consumes a CV, it does not edit one.
- The user wants competitive analysis of one named employer — use `explain` or web research instead.
- The user has not provided a CV or any preferences — the pipeline asks for them before invoking.

## Input

- `$ARGUMENTS` — the free-text preferences. Examples:
  - `"Senior backend, Go or Rust, remote from Berlin only, no crypto, no on-call"`
  - `"Part-time ML engineering, EU timezones, contract preferred"`
  - `"Frontend, React + TypeScript, hybrid in Lisbon, mid-level"`
- **CV path** — collected interactively via `AskUserQuestion` in Phase 0. Must be `.md` or `.txt`.

If `$ARGUMENTS` is empty, ask the user what kind of role they want and what constraints matter (employment type, remote vs hybrid vs on-site, region, salary floor, deal-breakers) before invoking.

## Scope Parameters

Extract scope modifiers from `$ARGUMENTS`, case-insensitive. Remaining text is the free-text preferences body (orthogonal to the modifiers).

- **`limit:<N>`** — maximum vacancies carried through the pipeline. Default: 50.
- **`recency:<N>d`** — only keep listings posted in the last N days. Default: 7.
- **`contacts:top<N>`** — number of top-scored jobs that get recruiter contact discovery. Default: 10.
- **`letters:top<N>`** — number of top-scored jobs that get a cover letter. Default: 10.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **preferences** — the full free-text body (everything not matching a parameter pattern).
- **limit** — optional, from `limit:<N>` (default: 50).
- **recency_days** — optional, from `recency:<N>d` (default: 7).
- **contacts_top_n** — optional, from `contacts:top<N>` (default: 10).
- **letters_top_n** — optional, from `letters:top<N>` (default: 10).

## Directory Structure

Two separate directories are used:

- **State** — `.mz/task/<task_name>/state.md`. Source of truth across phases; never rely on conversation memory.
- **Outreach data** — `.mz/outreach/<run_name>/` holds `search_strategy.json`, `sources.json`, temp `_scout/`, `raw_listings.json`, `scored_jobs.json`, `scored_jobs_excluded.json`, `letters/<job_slug>.md` files, and the final `<YYYY_MM_DD>_job_search_<slug>.md` report.

`task_name` follows the pattern `<YYYY_MM_DD>_job_search_<slug>`; `run_name` is `<YYYY_MM_DD>_job_search_<preferences_slug>`. Same-day collisions append `_v2`, `_v3`.

## Core Process

### Phase Overview

| #   | Phase                       | Agent(s)                              | Details                               |
| --- | --------------------------- | ------------------------------------- | ------------------------------------- |
| 0   | Setup + CV collection       | — (orchestrator)                      | Inline below                          |
| 1   | Strategy                    | `job-strategist`                      | `phases/strategy_and_sources.md`      |
| 1.5 | User approval of strategy   | — (orchestrator, AskUserQuestion)     | Inline below                          |
| 2   | Source assembly             | `job-source-researcher` (+ canonical) | `phases/strategy_and_sources.md`      |
| 3   | Scout fan-out               | N x `job-scout` (parallel)            | `phases/scout_score_enrich_report.md` |
| 4   | Normalize + filter          | — (orchestrator, inline)              | `phases/scout_score_enrich_report.md` |
| 4.5 | Cheap pre-score (LLM 0/1/2) | N x `job-prescorer` (parallel)        | `phases/scout_score_enrich_report.md` |
| 5   | Full score & rank           | N x `job-scorer` (parallel)           | `phases/scout_score_enrich_report.md` |
| 6   | Contacts (top-N)            | N x `job-contact-finder` (parallel)   | `phases/scout_score_enrich_report.md` |
| 7   | Cover letters (top-N)       | N x `job-letter-writer` (parallel)    | `phases/scout_score_enrich_report.md` |
| 8   | Master report               | `job-reporter`                        | `phases/scout_score_enrich_report.md` |

Read each phase file only when you reach the phase it covers. Do not read both phase files upfront.

### Strategy schema (Phase 1 output)

`search_strategy.json` carries the contract every downstream agent reads. New in this version:

- **`must_have_skills`** + **`must_have_or_groups`** — listings missing every must-have (or every member of an or-group) are hard-rejected by the scorer with `excluded_reason: "missing_must_have"`.
- **`nice_to_have_skills`** — credited in scoring but not gating.
- **`synonym_clusters`** — `{ canonical_skill: [cluster_terms...] }` map. The pre-scorer and scorer treat any cluster term as evidence of the parent skill.
- **`title_aliases`** — per-title fallback queries the scout uses when primary queries return < 5 hits per source (recall expansion).
- **`bilingual_query_variants`** — only present when the CV lists a non-English language at B2+. Scout picks language-matched queries for regional sources tagged with `language_hint`.

The legacy fields (`derived_from_cv`, `preferences`, `search_queries`, `location_eligibility_rule`, `scoring_weights`, `scoring_rationale`, `recency_window_days`, `notes`) all remain in place.

### Phase 1.5: User Approval of Strategy

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/outreach/<run_name>/search_strategy.json` with the Read tool. Capture the full file contents (derived job titles, must-have/nice-to-have skills, synonym clusters, title aliases, bilingual variants if present, region, employment-type filter, location-eligibility rule, scoring weights echo) into context. The strategy file is JSON — present it verbatim inside a fenced \`\`\`json block so structure is preserved.

**Surface 1 — emit the plan message.** Output the strategy verbatim as a normal markdown chat message. Emit the full verbatim contents of `.mz/outreach/<run_name>/search_strategy.json` — do not substitute a path, summary, or placeholder. Structure:

```
## Strategy ready for review — job-search

Built from your CV plus preferences. Derived titles, skills, region, location-eligibility rule, and source plan are below.

```json
<verbatim contents of search_strategy.json>
```

---
**Approve** → proceed to Phase 2 (source assembly + scout)  ·  **Reject** → task marked aborted, no scraping runs  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the strategy JSON in the question body, it lives in the plan message above:

- question: `The job-search strategy above is ready for review.`
- options:
  - **Approve** — proceed to Phase 2 (source assembly + scout)
  - **Reject** — mark the task aborted, no scraping runs

**Response handling**:

- **Approve** → update `.mz/task/<task_name>/state.md` `Phase` to `strategy_approved`, proceed to Phase 2.
- **Reject** → update `.mz/task/<task_name>/state.md` `Status` to `aborted_by_user` and stop.
- **Any other reply (feedback)** → re-dispatch `job-strategist` with the feedback appended, overwrite `search_strategy.json`, return to Surface 1, re-read `search_strategy.json`, and re-emit the full plan message from scratch with the new JSON contents — never diff-only, never summary-only. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — orchestration skill, not a discipline skill.

## Red Flags

- You dispatched scouts before the user approved the strategy.
- You used a banned data source (scraped LinkedIn profiles, AI-summarized aggregators, undated blog posts) or fabricated a vacancy that does not exist in search results.
- Master report lives in chat instead of `.mz/outreach/<run_name>/<YYYY_MM_DD>_job_search_<slug>.md`.
- A cover letter contains AI clichés ("excited to apply", "passionate", "leverage", "synergy") or fabricates experience absent from the CV.
- A remote job is marked eligible without verifying the listing permits work from the user's location.

## Verification

Before completing, output a visible block showing: run name, total listings scraped, listings excluded by location-eligibility, total ranked, top-1 final score, count of cover letters written, and the absolute path of the master report. Confirm the report file, scored JSON, and `letters/<slug>.md` files all exist on disk.

______________________________________________________________________

## Phase 0: Setup + CV collection

Parse arguments. Derive two names:

- `task_name` (state dir) = `<YYYY_MM_DD>_job_search_<slug>` where `<slug>` is a snake_case summary of the preferences (max 20 chars).
- `run_name` (outreach output dir) = `<YYYY_MM_DD>_job_search_<preferences_slug>`, max 40 chars. Example: `"Senior backend Go/Rust remote from Berlin"` → `2026_05_11_job_search_senior_be_berlin`.

```bash
mkdir -p .mz/task/<task_name>
mkdir -p .mz/outreach/<run_name>/letters
```

### CV collection

Invoke `AskUserQuestion` to collect the CV path. Acceptable formats: `.md`, `.txt`.

Pre-gate block emitted to chat:

```
**CV path needed**
The skill needs a path to your CV in markdown or plain text. PDF and DOCX are not supported in this version — convert first if needed.

- Provide an absolute or relative path to your `.md` or `.txt` CV
```

AskUserQuestion body:

```
What is the path to your CV file? Provide an absolute or relative path to a `.md` or `.txt` file. Type your answer or **Cancel** to abort.
```

Validation:

1. If the answer is "Cancel" → update `state.md` `Status` to `aborted_by_user`, stop.
1. If the file does not exist or is not `.md`/`.txt` → re-ask once with the error inlined; on a second failure, set `Status` to `aborted_missing_cv` and stop.
1. On success, read the CV and capture its absolute path.

### State file

Write `.mz/task/<task_name>/state.md`:

```yaml
schema_version: 2
Status: running
Phase: 0
Started: <ISO timestamp>
phase_complete: false
what_remains: []
Preferences: <free-text body>
CV path: <abs path>
Limit: 50
RecencyDays: 7
ContactsTopN: 10
LettersTopN: 10
RunName: <run_name>
```

After setup completes, read `phases/strategy_and_sources.md` and proceed to Phase 1.

______________________________________________________________________

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

______________________________________________________________________

## Resume Support

Before creating anything in Phase 0, check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` field and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent fails or returns empty: append an `Errors:` bullet in `state.md`, continue with available data.
- ALL agents in a phase fail (zero results): stop the pipeline and report the failure.
- Never fabricate data — incomplete results are better than false results.
- An agent returns `STATUS: NEEDS_CONTEXT` for missing user input (e.g. no location in CV but remote-only preferences): invoke `AskUserQuestion` to fill the gap, then re-dispatch.
