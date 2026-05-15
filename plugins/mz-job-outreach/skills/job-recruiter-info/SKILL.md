---
name: job-recruiter-info
description: ALWAYS invoke when the user wants to find recruiter, hiring-manager, or careers contacts for a single job listing or company — outside the full /job-search pipeline. Triggers: "find a recruiter", "find recruiter contacts", "find hiring manager", "who recruits for X", "careers email for X", "who do I apply to at X".
argument-hint: "<job listing URL or company name>" [region:<region>] [language:<lang>]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Job Recruiter Info

## Overview

You are an orchestrator that runs a one-shot recruiter-contact lookup for a single job target. Given a job listing URL or a company name plus an optional role hint, you dispatch the `job-contact-finder` agent against that target and produce a compact markdown report containing the named recruiter (if any), careers-page email, LinkedIn company page, generic-pattern guesses, apply URL, and a confidence assessment.

This is the standalone counterpart to Phase 6 of `/job-search`. Use it when the user already has a target job and only needs the contacts — no CV, no scoring, no cover letter, no pipeline state.

## When to Use

Invoke when the user wants apply-target contacts for one job or one company without running the full job-search pipeline. Trigger phrases: "find a recruiter for this role", "who do I apply to at <company>", "careers email for <company>", "hiring manager for this listing", "find the recruiter".

### When NOT to use

- The user wants to scan many jobs against a CV — use `/job-search`.
- The user wants company contacts for B2B outreach (sales, partnerships) — use `/outreach-research` (full pipeline) or `/outreach-enrich-company` (deepen an existing card) in mz-biz-outreach.
- The user wants to draft a cover letter for that role — use the copywrite skill from mz-creative.
- The user wants to investigate the company itself (reputation, growth, tech) — use `/outreach-research` for a single-company scan.

## Input

- `$ARGUMENTS` — Free-text identifying the target. Either:
  - A canonical job listing URL (`https://jobs.lever.co/...`, `https://boards.greenhouse.io/...`, LinkedIn job link, etc.), OR
  - A company name plus an optional role hint (e.g. `"Acme Corp — Senior Backend Engineer"` or just `"Acme Corp"`).
- Optional modifiers (case-insensitive):
  - `region:<value>` — geographic hint for disambiguation (e.g. `region:DACH`, `region:EU`).
  - `language:<value>` — language hint when the user expects non-English recruiter contacts (e.g. `language:de`, `language:fr`).

If `$ARGUMENTS` is empty, ask the user for a job URL or a company name before invoking.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **target** — the listing URL or company name (everything not matching a parameter pattern).
- **role_hint** — optional, the role description if combined with a company name (split on `—`, `-`, `:`, or `,`).
- **region** — optional, from `region:<value>` (default: derived from the listing URL host or the company domain TLD).
- **language** — optional, from `language:<value>` (default: `en`).

## Directory Structure

- **State** — `.mz/task/<task_name>/state.md`. Source of truth across phases.
- **Output** — `.mz/outreach/<run_name>/` holds `target.json` (parsed target), `contacts.json` (raw agent output), and the final `<YYYY_MM_DD>_recruiter_info_<slug>.md` report.

`task_name` follows `<YYYY_MM_DD>_job_recruiter_info_<slug>`; `run_name` is `<YYYY_MM_DD>_job_recruiter_info_<slug>` (same leading-date convention; max 40 chars). Same-day collisions append `_v2`, `_v3`.

## Core Process

### Phase Overview

| #   | Phase                   | Agent(s)             | Details                       |
| --- | ----------------------- | -------------------- | ----------------------------- |
| 0   | Setup + target parsing  | — (orchestrator)     | Inline below                  |
| 1   | Contact lookup          | `job-contact-finder` | `phases/lookup_and_report.md` |
| 2   | Compact markdown report | — (orchestrator)     | `phases/lookup_and_report.md` |

Read `phases/lookup_and_report.md` when you reach Phase 1.

### Phase 0: Setup + target parsing

Parse arguments. Derive:

- `task_name` (state dir) = `<YYYY_MM_DD>_job_recruiter_info_<slug>` where `<slug>` is a snake_case summary of the target (max 20 chars, derived from company name or listing host).
- `run_name` (outreach output dir) = `<YYYY_MM_DD>_job_recruiter_info_<slug>` (max 40 chars).

```bash
mkdir -p .mz/task/<task_name>
mkdir -p .mz/outreach/<run_name>
```

Detect input shape:

- **URL** — `target` matches `^https?://`. WebFetch the page once to extract: `company`, `role_title`, `location_string`, `summary_snippet`. If WebFetch fails, fall back to the URL host as the company hint and surface the failure as a `DONE_WITH_CONCERNS` note in the final report.
- **Company name (with optional role hint)** — Use `target` as `company`; use `role_hint` as `role_title` if provided. Derive the company domain via WebSearch (`"<company>" official site`); first authoritative result is the domain.

Write `.mz/outreach/<run_name>/target.json`:

```json
{
  "input_type": "url" or "company",
  "input_raw": "<original argument>",
  "company": "<resolved company name>",
  "role_title": "<resolved role title or null>",
  "listing_url": "<resolved URL or null>",
  "company_domain": "<resolved domain or null>",
  "location_string": "<from listing or null>",
  "summary_snippet": "<from listing or null>",
  "region": "<from arg or inferred or null>",
  "language": "<from arg or 'en'>"
}
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Job Recruiter Info State
- **Status**: running
- **Phase**: 0
- **Started**: <ISO timestamp>
- **Target**: <input_raw>
- **InputType**: <url|company>
- **Company**: <resolved company>
- **RoleTitle**: <resolved role or null>
- **RunName**: <run_name>
```

After setup completes, read `phases/lookup_and_report.md` and proceed to Phase 1.

## Techniques

Techniques: delegated to `phases/lookup_and_report.md`.

## Common Rationalizations

N/A — orchestration skill, not a discipline skill.

## Red Flags

- You fabricated a recruiter name or email that did not appear in any verified source.
- You included a `noreply@`, `no-reply@`, `donotreply@`, `mailer-daemon@`, or `postmaster@` address in the report.
- Marked `confidence: high` without a named recruiter AND a verified email (verified means seen on the listing, careers page, or a named LinkedIn handle).
- Followed a LinkedIn profile URL deep into the platform (only the search-results page is allowed per agent rules).
- Report lives in chat instead of `.mz/outreach/<run_name>/<YYYY_MM_DD>_recruiter_info_<slug>.md`.

## Verification

Before completing, output a visible block showing: target (company + role if known), confidence level (`high`/`medium`/`low`), whether a named recruiter was found, careers-page email status (`verified`/`guessed`/`none`), and the absolute path of the report. Confirm both `contacts.json` and the report file exist on disk.

## Resume Support

Before creating anything in Phase 0, check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` field and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent returns empty: append an `Errors:` bullet in `state.md`, write a report that explicitly says "no contacts surfaced" with the `ZERO RESULTS VERIFIED` or `ZERO RESULTS UNVERIFIED` disclosure tag from the agent.
- Agent returns `STATUS: NEEDS_CONTEXT`: invoke `AskUserQuestion` to fill the missing field (typically the company domain), then re-dispatch.
- Agent returns `STATUS: BLOCKED`: stop the pipeline, set state `Status` to `failed_blocked`, surface the cause to the user.
- Never fabricate data — incomplete results are better than false results.
- Listing URL was provided but unreachable: degrade to `input_type: company`, surface the WebFetch failure in the final report.
