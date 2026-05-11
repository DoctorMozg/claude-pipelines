# Phase 1: Contact Lookup — Phase 2: Report

## Phase 1: Contact lookup

Dispatch a single `outreach-contact-finder` agent against the resolved company. The agent expects a company JSON with scout + scan data; for this skill we build a minimal stub so the same agent contract works without modification.

### 1.1 Build a minimal company JSON stub

Read `<RUN_DIR>/target.json`. Write `<RUN_DIR>/_stub/company.json`:

```json
{
  "name": "<target.company>",
  "domain": "<target.domain>",
  "sector": "<target.sector_hint or 'unknown'>",
  "location": "<target.region or 'unknown'>",
  "founded": null,
  "description": null,
  "reviews": null,
  "review_summary": null,
  "contacts": null
}
```

Write a minimal strategy stub at `<RUN_DIR>/_stub/strategy.json` so the agent can read priority decision-makers:

```json
{
  "target_profile": {
    "decision_maker_priorities": <target.decision_maker_priorities array>,
    "outreach_angle": "ad-hoc contact discovery"
  }
}
```

### 1.2 Dispatch `outreach-contact-finder`

Dispatch one agent (no waves needed — single target):

```
Find contacts and decision-makers for this company.

Company file (input): <RUN_DIR>/_stub/company.json
Strategy file: <RUN_DIR>/_stub/strategy.json
Output file: <RUN_DIR>/_contacts/single.json

Find key people (named decision-makers with LinkedIn profiles), email
addresses (info@, sales@, contact@, and any verified person-specific
addresses), phone numbers, and social presence (LinkedIn company page,
Twitter/X, etc.).

Prioritize the decision-maker roles in strategy.target_profile
.decision_maker_priorities. Cap at 5 key people.

Public information only. Do not guess individual email patterns. Do not
scrape private LinkedIn profiles — search-result snippets and public
profile pages only.
```

The agent writes `<RUN_DIR>/_contacts/single.json`. Move it to `<RUN_DIR>/contacts.json` and delete `_contacts/` and `_stub/`.

Update `state.md` `Phase` field to `contacts_complete`.

### 1.3 Handle agent status

- `STATUS: DONE` — proceed.
- `STATUS: DONE_WITH_CONCERNS` — surface concerns in the final report under a `## Concerns` section; proceed.
- `STATUS: NEEDS_CONTEXT` — invoke `AskUserQuestion` to fill the missing field (typically a clarifying detail about the company), patch `target.json`, re-dispatch once. If it returns `NEEDS_CONTEXT` again, set state `Status` to `failed_missing_context` and stop.
- `STATUS: BLOCKED` — set state `Status` to `failed_blocked`, surface the cause, stop.

______________________________________________________________________

## Phase 2: Compact markdown report

Read `<RUN_DIR>/contacts.json` and `<RUN_DIR>/target.json`. Write the final report to:

```
<RUN_DIR>/<YYYY_MM_DD>_outreach_contacts_<slug>.md
```

(Append `_v2`, `_v3` on same-base-name collision.)

Report skeleton:

```markdown
# Outreach Contacts — <company>

- **Target**: `<target.input_raw>`
- **Company**: <target.company>
- **Domain**: <target.domain>
- **Sector hint**: <target.sector_hint or "_unknown_">
- **Region**: <target.region or "_n/a_">
- **Priority decision-makers**: <comma-joined target.decision_maker_priorities>

## Key people

<For each entry in contacts.contacts.key_people, formatted as:>

### <name> — <title>
- **LinkedIn**: <linkedin or "_n/a_">
- **Email**: <email or "_not publicly listed_">
- **Relevance**: <relevance line>

<If key_people is empty: "No named decision-makers surfaced from public sources. See generic patterns below as last-resort fallbacks.">

## Direct contact channels

- **Emails (verified)**: <bulleted contacts.contacts.emails; if empty: "_none verified_">
- **Phone numbers**: <bulleted contacts.contacts.phones; if empty: "_n/a_">
- **WhatsApp Business**: <contacts.contacts.whatsapp or "_n/a_">
- **Booking link**: <contacts.contacts.booking_link or "_n/a_">
- **Office address**: <contacts.contacts.address or "_n/a_">

## Social presence

- **LinkedIn company page**: <contacts.contacts.social.linkedin_company or "_n/a_">
- **Twitter / X**: <contacts.contacts.social.twitter or "_n/a_">
- **Other**: <any extra social channels found, or "_n/a_">

## Concerns (if any)
<Only present if the agent emitted DONE_WITH_CONCERNS or surfaced caveats;
otherwise omit the section entirely.>

## Methodology

- Source priority: official company pages (About, Team, Leadership, Contact) → official public profiles (LinkedIn company/person, GitHub orgs) → first-party partner pages (VC portfolios, conference speakers) → dated reputable news.
- Banned sources: Stack Overflow snippets, AI-generated summaries, undated blog posts, scraped lead lists, social posts without verifiable source trail.
- Public information only — no scraped private profiles, no guessed personal email patterns.
- 2 verified contacts > 5 uncertain ones. Empty fields are left null rather than fabricated.
```

After writing the report:

1. Update `state.md` — set `Phase` to `complete` and add `CompletedAt: <ISO timestamp>` and `KeyPeopleFound: <count>`.
1. Display to the user the verification block from `SKILL.md` §Verification:
   - Target (company + domain)
   - Count of named decision-makers
   - Count of verified emails
   - Count of phone numbers
   - Social-presence coverage summary
   - Absolute path of the report
