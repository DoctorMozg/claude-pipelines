# Phase 1: Contact Lookup — Phase 2: Report

## Phase 1: Contact lookup

Dispatch a single `job-contact-finder` agent against the resolved target. The agent expects a `scored_jobs.json` path with an entry index in the canonical `/job-search` flow; for this skill we build a single-entry stub so the same agent contract works without modification.

### 1.1 Build a single-entry job record stub

Read `<RUN_DIR>/target.json`. Write `<RUN_DIR>/scored_jobs.json` as a one-element array:

```json
[
  {
    "company": "<target.company>",
    "url": "<target.listing_url or '<unknown>'>",
    "location_string": "<target.location_string or null>",
    "source": "ad-hoc",
    "summary_snippet": "<target.summary_snippet or null>"
  }
]
```

Write a minimal `<RUN_DIR>/search_strategy.json` to satisfy the agent's region/language input:

```json
{
  "region": "<target.region or null>",
  "language": "<target.language or 'en'>"
}
```

### 1.2 Dispatch `job-contact-finder`

Dispatch one agent (no waves needed — single target):

```
Find recruiter/hiring-manager contacts for this job.

Job record: <RUN_DIR>/scored_jobs.json (entry index 0)
Company: <target.company>
Listing URL: <target.listing_url or 'unknown — derive from company domain'>
Strategy file: <RUN_DIR>/search_strategy.json
Output file: <RUN_DIR>/_contacts/single.json

Fetch the listing page if a URL is available, then walk the fallback chain:
named recruiter on posting -> company careers page -> LinkedIn search for
"<company> recruiter" -> generic email patterns (careers@, jobs@, talent@,
hr@ + domain) -> company contact form.

Filter out noreply@, no-reply@, mailer-daemon@, donotreply@, postmaster@.

Emit the contacts object with named_recruiter (if found), careers_page_email,
linkedin_company, generic_pattern_guesses, apply_url, confidence, and notes.
```

The agent writes `<RUN_DIR>/_contacts/single.json`. Move it to `<RUN_DIR>/contacts.json` and delete `_contacts/`.

Update `state.md` `Phase` field to `contacts_complete`.

### 1.3 Handle agent status

- `STATUS: DONE` — proceed.
- `STATUS: DONE_WITH_CONCERNS` — surface the concerns in the final report under a `## Concerns` section; proceed.
- `STATUS: NEEDS_CONTEXT` — invoke `AskUserQuestion` with the missing field (typically `company_domain`), patch `target.json`, re-dispatch once. If it returns `NEEDS_CONTEXT` again, set state `Status` to `failed_missing_context` and stop.
- `STATUS: BLOCKED` — set state `Status` to `failed_blocked`, surface the cause to the user, stop.

______________________________________________________________________

## Phase 2: Compact markdown report

Read `<RUN_DIR>/contacts.json` and `<RUN_DIR>/target.json`. Write the final report to:

```
<RUN_DIR>/<YYYY_MM_DD>_recruiter_info_<slug>.md
```

(Append `_v2`, `_v3` on same-base-name collision.)

Report skeleton:

```markdown
# Recruiter Info — <company> <role_title?>

- **Target**: `<target.input_raw>`
- **Company**: <target.company>
- **Role**: <target.role_title or "_unspecified_">
- **Listing URL**: <target.listing_url or "_n/a_">
- **Company domain**: <target.company_domain or "_unknown_">
- **Region / language**: <target.region or "_n/a_"> / <target.language>
- **Confidence**: **<contacts.confidence>**

## Named recruiter
<contacts.named_recruiter formatted as: Name, Title (if known), LinkedIn, Email, Source.
If null: "No named recruiter surfaced from posting, careers page, or LinkedIn search."

## Apply route
- **Apply URL**: <contacts.apply_url or "_n/a_">
- **Careers-page email (verified)**: <contacts.careers_page_email or "_none verified_">
- **LinkedIn company page**: <contacts.linkedin_company or "_n/a_">

## Generic-pattern guesses (NOT verified)
<bulleted list of contacts.generic_pattern_guesses; if empty: "No generic patterns derivable — domain unknown.">

> These addresses are derived from the domain only and have not been observed
> on the company's pages. Treat as last-resort fallbacks.

## Notes
<contacts.notes verbatim>

## Concerns (if any)
<Only present if the agent emitted DONE_WITH_CONCERNS or a ZERO RESULTS disclosure;
otherwise omit the section entirely.>

## Methodology

- Source priority: listing page → company careers page → LinkedIn search-results page → generic pattern fallback.
- Filtered prefixes: `noreply@`, `no-reply@`, `mailer-daemon@`, `donotreply@`, `do-not-reply@`, `postmaster@`, `abuse@`.
- Public information only — no scraped private LinkedIn profiles, no paid aggregator data.
- Confidence: `high` requires a named recruiter AND a verified email; `medium` is one of the two; `low` is generic patterns or contact form only.
```

After writing the report:

1. Update `state.md` — set `Phase` to `complete` and add `CompletedAt: <ISO timestamp>` and `Confidence: <value>`.
1. Display to the user the verification block from `SKILL.md` §Verification:
   - Target (company + role if known)
   - Confidence level
   - Whether a named recruiter was found
   - Careers-page email status
   - Absolute path of the report
