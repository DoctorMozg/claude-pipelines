---
name: outreach-contacts
description: ALWAYS invoke when the user wants to find decision-makers, emails, or contact paths for a single company — outside the full /outreach-research pipeline. Triggers: "find contacts", "who do I write to at X", "find decision makers", "company emails", "CEO/CTO email for X", "find a person to email at X".
argument-hint: "<company name or domain>" [decision_makers:<roles>] [region:<region>]
model: sonnet
allowed-tools: Agent, AskUserQuestion, Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
---

# Outreach Contacts

## Overview

You are an orchestrator that runs a one-shot company-contact lookup for a single B2B target. Given a company name or domain plus an optional list of priority decision-maker roles, you dispatch the `outreach-contact-finder` agent against that company and produce a compact markdown report with named decision-makers, emails, phone numbers, social presence, and an apply-route summary.

This is the standalone counterpart to the `outreach-contact-finder` step inside `/outreach-research` enrichment. Use it when the user already has a target company list and only needs the contacts — no scoring, no reputation scan, no growth/news/tech enrichment.

## When to Use

Invoke when the user wants decision-maker contacts for one company without running the full outreach-research pipeline. Trigger phrases: "find contacts at <company>", "who do I write to at <company>", "find the CEO email for <company>", "find decision makers at <company>", "give me contacts for <company>".

### When NOT to use

- The user wants to discover companies first — use `/outreach-research`.
- The user wants recruiter contacts for a job application — use `/job-recruiter-info` in mz-job-outreach.
- The user wants to draft an outreach message — use the copywrite skill from mz-creative.
- The user wants full intelligence on the company (reputation, growth, tech, news) — use `/outreach-research` with `limit:1` on a single-name target.

## Input

- `$ARGUMENTS` — Free-text identifying the target. Either:
  - A company name (e.g. `"Acme Corp"`), OR
  - A company domain (e.g. `acme.com`).
- Optional modifiers (case-insensitive):
  - `decision_makers:<roles>` — comma-separated priority roles (e.g. `decision_makers:CTO,VP-Engineering,Head-of-Platform`). Default: inferred from the target context (CEO/CTO/founder for small companies; VP/Head-of-X for larger ones).
  - `region:<value>` — geographic hint for disambiguation when the company name is ambiguous (e.g. `region:DACH`, `region:LATAM`).

If `$ARGUMENTS` is empty, ask the user for a company name or domain before invoking.

## Argument Parsing

Extract from `$ARGUMENTS`:

- **target** — the company name or domain (everything not matching a parameter pattern).
- **decision_makers** — optional comma-split list from `decision_makers:<value>` (default: inferred).
- **region** — optional, from `region:<value>` (default: inferred from the domain TLD or company description).

## Directory Structure

- **State** — `.mz/task/<task_name>/state.md`. Source of truth across phases.
- **Output** — `.mz/outreach/<run_name>/` holds `target.json` (parsed target + role priorities), `contacts.json` (raw agent output), and the final `<YYYY_MM_DD>_outreach_contacts_<slug>.md` report.

`task_name` follows `<YYYY_MM_DD>_outreach_contacts_<slug>`; `run_name` is `<YYYY_MM_DD>_outreach_contacts_<slug>` (same leading-date convention; max 40 chars). Same-day collisions append `_v2`, `_v3`.

## Core Process

### Phase Overview

| #   | Phase                     | Agent(s)                  | Details                       |
| --- | ------------------------- | ------------------------- | ----------------------------- |
| 0   | Setup + target resolution | — (orchestrator)          | Inline below                  |
| 1   | Contact lookup            | `outreach-contact-finder` | `phases/lookup_and_report.md` |
| 2   | Compact markdown report   | — (orchestrator)          | `phases/lookup_and_report.md` |

Read `phases/lookup_and_report.md` when you reach Phase 1.

### Phase 0: Setup + target resolution

Parse arguments. Derive:

- `task_name` (state dir) = `<YYYY_MM_DD>_outreach_contacts_<slug>` where `<slug>` is a snake_case summary of the company (max 20 chars, derived from name or domain stem).
- `run_name` (outreach output dir) = `<YYYY_MM_DD>_outreach_contacts_<slug>` (max 40 chars).

```bash
mkdir -p .mz/task/<task_name>
mkdir -p .mz/outreach/<run_name>
```

Resolve the target:

- **Domain input** — `target` matches a domain pattern (`*.tld`). The company name is derived via WebFetch of `https://<domain>` and reading the `<title>` tag plus the About/Team page if present.
- **Name input** — `target` is a company name. Derive the company domain via WebSearch (`"<company>" official site`); first authoritative result wins. If multiple plausible candidates surface, invoke `AskUserQuestion` with the top-3 candidates so the user picks the correct one.

Write `.mz/outreach/<run_name>/target.json`:

```json
{
  "input_type": "name" or "domain",
  "input_raw": "<original argument>",
  "company": "<resolved company name>",
  "domain": "<resolved domain>",
  "sector_hint": "<inferred or null>",
  "region": "<from arg or inferred or null>",
  "decision_maker_priorities": ["CEO", "CTO", "VP Engineering", ...]
}
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Outreach Contacts State
- **Status**: running
- **Phase**: 0
- **Started**: <ISO timestamp>
- **Target**: <input_raw>
- **InputType**: <name|domain>
- **Company**: <resolved company>
- **Domain**: <resolved domain>
- **RunName**: <run_name>
```

After setup completes, read `phases/lookup_and_report.md` and proceed to Phase 1.

## Techniques

Techniques: delegated to `phases/lookup_and_report.md`.

## Common Rationalizations

N/A — orchestration skill, not a discipline skill.

## Red Flags

- You fabricated a decision-maker name or email that did not appear in any verified source.
- You scraped a private LinkedIn profile — only search-result snippets and public profile pages are allowed.
- You guessed an individual's email address from a domain pattern and presented it as verified — guessed addresses go in the generic-patterns block, not the named-people block.
- Report lives in chat instead of `.mz/outreach/<run_name>/<YYYY_MM_DD>_outreach_contacts_<slug>.md`.
- You linked a key person who has publicly left the company.

## Verification

Before completing, output a visible block showing: target (company + domain), count of named decision-makers found, count of verified emails, count of phone numbers, social-presence coverage (LinkedIn / X / other), and the absolute path of the report. Confirm both `contacts.json` and the report file exist on disk.

## Resume Support

Before creating anything in Phase 0, check if `.mz/task/<task_name>/state.md` exists for the resolved `task_name`. If it does, read the `Phase` field and resume from the next incomplete phase. All phases are idempotent — re-running overwrites output files.

## Error Handling

- Agent returns empty: append an `Errors:` bullet in `state.md`, write a report that explicitly says "no contacts surfaced" with the agent's status note.
- Agent returns `STATUS: NEEDS_CONTEXT`: invoke `AskUserQuestion` to fill the missing field (typically the company domain), then re-dispatch.
- Agent returns `STATUS: BLOCKED`: stop the pipeline, set state `Status` to `failed_blocked`, surface the cause to the user.
- Never fabricate data — incomplete results are better than false results.
- Ambiguous company name (multiple candidate domains): escalate via `AskUserQuestion` with the top-3 candidates rather than guessing.
