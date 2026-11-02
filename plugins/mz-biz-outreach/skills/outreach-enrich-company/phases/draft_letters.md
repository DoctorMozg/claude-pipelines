# Phase 3: Draft Letters

Read `SKILL.md` first. This file picks up after either:

- **Phase 2 complete** (`enrichment_complete`) — `enrich_mode` is `both` (run drafting + card rewrite with both sections) or `only` (skip drafting/naturalize, run only Phase 5 with deeper intel).
- **Phase 1 complete** (`card_parsed`) — `enrich_mode` is `skip` (no Phase 2; run Phase 3 → 4 → 5 with letters only).

## Phase 3: Draft letters (expert-copywriter)

Skipped entirely when `enrich_mode == "only"`.

### 3.0 Build per-contact briefs

Brief-building moved out of Phase 1 (which now only parses the card and writes `card_parsed.json`). Read inputs:

1. `<PROJECT_ROOT>/.mz/task/<task_name>/card_parsed.json` — written in Phase 1.
1. `<PROJECT_ROOT>/.mz/task/<task_name>/enrichment/*.json` — written in Phase 2 (skip if `enrich_mode == "skip"`; the directory will be empty).
1. `<PROJECT_ROOT>/.mz/task/<task_name>/deeper_intelligence.md` — written in Phase 2 (skip if `enrich_mode == "skip"`).
1. The orchestrator's in-memory light-pass results from Phase 1 (per-contact public-activity strings).
1. Sender voice + outreach angles resolved in Phase 1.

For each of the (up to 5) Key Contacts from `card_parsed.json`, decide the channel:

- If `channels_override == "email"` → channel = `email` (requires the contact's email to be known, else fall back to LinkedIn DM if URL known, else `skip`).
- If `channels_override == "linkedin"` → channel = `linkedin_dm` (requires LinkedIn URL, else `skip`).
- If `channels_override == "both"` → emit TWO briefs per contact when both handles exist: one `email`, one `linkedin_dm`. Skip a missing channel cleanly.
- If no override (default) → prefer `email` when an email is known; else `linkedin_dm` when LinkedIn URL is known; else `skip` and record the reason.

Per-channel handle resolution: the card lists contact emails in the `## Key Contacts` block's `**Emails**:` line — these are company-level (info@, sales@). Person-specific emails appear in the per-contact line only if the card found one. If only generic emails exist, mark the channel as `email_generic` and target the generic address with the contact named in the body.

For each non-skipped (contact, channel) pair, write `<PROJECT_ROOT>/.mz/task/<task_name>/briefs/<channel>_<contact_slug>.json`:

```json
{
  "company": {
    "name": "<from card>",
    "slug": "<company_slug>",
    "domain": "<from card>",
    "sector": "<from card>"
  },
  "recipient": {
    "name": "<full name>",
    "first_name": "<first name only>",
    "title": "<title from card>",
    "linkedin_url": "<url or null>",
    "email": "<email or null>",
    "relevance": "<relevance line from card>"
  },
  "chosen_channel": "email | email_generic | linkedin_dm",
  "channel_constraints": {
    "subject_max_chars": 55,
    "body_word_min": 120,
    "body_word_max": 180
  },
  "chosen_angle": "<one line from outreach_angles, picked to fit this contact>",
  "value_claim": "<one short sentence — the user-facing benefit, derived from strategy.outreach_angles + card outreach_recommendation>",
  "company_hook": "<one line from the card's Outreach Recommendation Best angle, paraphrased to fit this contact>",
  "personalization_hooks": [
    {
      "signal": "<verbatim signal>",
      "source": "card | light_pass | deeper_intel",
      "source_detail": "<which card section, which URL, or which enrichment file>",
      "verified": true
    }
  ],
  "card_recent_news": [
    {
      "title": "<news title>",
      "date": "<date>",
      "outreach_implication": "<implication line from card>"
    }
  ],
  "climate_context": {
    "industry": "<matched combo industry or null>",
    "region": "<matched combo region or null>",
    "angles": ["<top_outreach_angles from the matched climate combo, if brief_run supplied>"],
    "signals": ["<dated climate signal + its outreach_implication, if any>"]
  },
  "reader_style": {
    "social_style": "<Driver | Analytical | Amiable | Expressive | null - populated in 3.0a by the profiler wave; null when personality_mode is off or no footprint cue exists>",
    "role_priorities": ["<what the recipient's role tends to prioritize, e.g. cost/ROI, technical fit, reach>"],
    "confidence": "<high | med | low | none>",
    "calibration_directive": "<2-4 imperative lines: structure, length-bias, pacing, which angle leads first - never names the trait>",
    "evidence": [{ "cue": "<observable footprint cue>", "source_url": "<url>" }]
  },
  "verified_entities": [
    "<every proper noun, product name, metric, date, URL the copywriter is allowed to reference — populated from card + light pass + deeper intel>"
  ],
  "strategy_source": "strategy.json | default | sender_override",
  "sender_voice": "<3–5 line voice description>",
  "channel_format_rules": "<copied verbatim from the channel rules table below so the copywriter sees them inline>"
}
```

`channel_constraints` for `linkedin_dm`: `{ "subject_max_chars": 0, "body_word_min": 60, "body_word_max": 100 }`. For `email_generic`: same as `email` plus a `body_must_name_recipient: true` flag so the copywriter addresses the contact in the body even though the To: is generic.

**Deeper-intel integration** (when `enrich_mode in (both, only)` and Phase 2 ran successfully):

For each contact:

- Read `enrichment/news.json`. Add any items with `outreach_implication` set as additional `card_recent_news` entries; promote their proper nouns/metrics/URLs into `verified_entities`. Tag added hooks with `source: "deeper_intel"`, `source_detail: "news.json: <title>"`.
- Read `enrichment/tech.json`. Add any product/framework/repo names to `verified_entities`. If a recent eng-blog post or GitHub repo lines up with the contact's title (e.g. CTO + a recent infra-migration post), add it as a `personalization_hooks` entry tagged `source: "deeper_intel"`, `source_detail: "tech.json: <ref>"`.
- Read `enrichment/growth.json`. Add the numeric quote (open role count, headcount range, funding stage) to `verified_entities`. If the contact's title makes growth-signals relevant (e.g. VP Eng + headcount delta), add it as a hook.
- Read `enrichment/reputation.json`. Add at most ONE per-platform sentiment-themed signal as a hook only if it would be appropriate to cite in cold outreach (e.g. Glassdoor "great engineering culture" theme for a recruiter angle). Skip negative-sentiment items entirely.
- Read `enrichment/contacts.json`. Look for per-contact public-activity signals (recent post, talk, GitHub contribution, podcast) attached to this contact's name. Add as hooks tagged `source: "deeper_intel"`, `source_detail: "contacts.json: <activity ref>"`. Skip items where `verified: false`.

When `enrich_mode == "skip"`, the deeper-intel integration is a no-op (the directory is empty).

**Local-climate integration** (when `brief_run` was supplied and Phase 1 set `climate_context`): add `climate_context.angles` as candidate values for each contact's `chosen_angle`, and promote any dated fact inside `climate_context.signals` into `verified_entities`. Tag a climate-derived opening hook `source: "climate"`, `source_detail: "climate.json: <industry> × <region>"`. This lets a letter lead with local-market context while staying inside the verified-entities rule. Independent of `enrich_mode` — climate comes from the brief run, not Phase 2.

Write each brief with `reader_style` as a null placeholder (`social_style: null`, `confidence: "none"`, empty `evidence`, empty `calibration_directive`); step 3.0a fills it in.

Update `state.md` Phase field to `briefs_complete`, append a `Briefs` list (one path per file).

### 3.0a Reader-style profiling wave (outreach-personality-profiler)

Skipped entirely when `personality_mode == "off"` (the brief's `reader_style` stays the null placeholder and letters read exactly as they did before this step existed). Otherwise runs automatically — no approval gate.

This wave calibrates each letter to how the recipient prefers to be addressed, using the Social Styles model (Driver / Analytical / Amiable / Expressive). It is grounded-only: a style is asserted solely when a citable public-footprint cue supports it; otherwise the read falls back to role-based priorities and never guesses a personality from a title.

For each brief whose `chosen_channel` is not `skip` (dedupe by contact — one profile per person even when both an email and a DM brief exist), dispatch one `outreach-personality-profiler`. Dispatch in parallel waves of at most 6 concurrent agents per wave; up to 5 contacts fit in one wave. Wait for every agent in the wave to report, then check that each profile exists on disk before using it.

Output path per contact: `<PROJECT_ROOT>/.mz/task/<task_name>/profiles/<contact_slug>.json`.

Dispatch prompt (`subagent_type: outreach-personality-profiler`):

```
Profile the communication style of this single contact for letter calibration.

Contact:
  - Name: <recipient.name>
  - Title: <recipient.title>
  - Company: <company.name>
  - LinkedIn: <recipient.linkedin_url or "unknown">
Seed signal (already gathered, may be empty): <the Phase 1 light-pass public-activity
  string for this contact, plus any contacts.json activity reference tagged to this name>
Recency window: 12 months.
Output file: <PROJECT_ROOT>/.mz/task/<task_name>/profiles/<contact_slug>.json

Assert a Social Style ONLY with at least one citable public-footprint cue. With no
citable cue, leave social_style null and populate role_priorities from the title.
Emit a calibration_directive that shapes structure, length-bias, pacing, and which
angle leads - never naming or alluding to the trait, never touching the salutation,
sign-off, or voice register. At most 3 web calls. Professional signal only.
```

After each profiler returns: read its `profiles/<contact_slug>.json` and merge `social_style`, `role_priorities`, `confidence`, `calibration_directive`, and `evidence` into the `reader_style` block of every brief for that contact (both channels if two exist). On `BLOCKED` / `NEEDS_CONTEXT`, leave that contact's `reader_style` as the null placeholder (the letter falls back to neutral structure) and record `profile_failed: <contact_slug>` in `state.md` — do not auto-retry, do not block the run.

Update `state.md`: append a `Profiles` list (one path per profiled contact with its `social_style`/`confidence` or `fallback:role_priorities`), and record `ProfilesFootprint` (count with a citable style) and `ProfilesRolePriority` (count that fell back).

### 3.1 Dispatch plan

Read every brief file under `<PROJECT_ROOT>/.mz/task/<task_name>/briefs/`. For each brief whose `chosen_channel` is not `skip`, dispatch one `expert-copywriter` agent. Dispatch in parallel waves of at most 6 concurrent agents per wave. Wait for every agent in the wave to report, then check that each draft exists on disk before using it. Start the next wave only after that.

Per-brief output path: `<PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md` (use `<channel>_<contact_slug>` from the brief filename).

### 3.2 Channel rules table

Pass these constraints verbatim inside the dispatch so the agent does not improvise structure:

| Field               | `email` / `email_generic`                                                                                                                                                                                                                                                                                                                                                            | `linkedin_dm`                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Frontmatter         | YAML block at top with `subject`, `channel: email` (or `email_generic`), `recipient: <full name>`                                                                                                                                                                                                                                                                                    | YAML block at top with `channel: linkedin_dm`, `recipient: <full name>`, no `subject` key |
| Body length         | 120-180 words (excludes the salutation and sign-off lines)                                                                                                                                                                                                                                                                                                                           | 60-100 words (excludes the salutation and sign-off lines)                                 |
| Subject line        | First field in the frontmatter. \<=55 chars, about 6-7 words. Specific verb + named outcome. No clickbait, no emoji.                                                                                                                                                                                                                                                                 | None (LinkedIn DMs have no subject field)                                                 |
| Salutation          | One greeting line, voice-adaptive: `Hi <first>,` (warm) / `Hello <first>,` (neutral) / `Dear <title last>,` (formal). For `email_generic` keep `Hi <first>,` when the name is known, else `Hello,`. Does not count as the opening sentence.                                                                                                                                          | Casual only: `Hi <first>,`. Never a formal `Dear ...` on a DM.                            |
| Opening sentence    | The line after the salutation. References exactly ONE personalization hook from `brief.personalization_hooks[*]`, verbatim or near. The salutation does not satisfy this.                                                                                                                                                                                                            | Same rule.                                                                                |
| CTA                 | One imperative sentence near the end. One ask, low friction (15-min call, reply Y/N, share thoughts).                                                                                                                                                                                                                                                                                | Same rule.                                                                                |
| Sign-off            | Two lines: a voice-adaptive gratitude close, then the sender's first name. Map by voice: warm -> `Thanks,`; neutral -> `Best regards,`; formal -> `Sincerely,`. One thanks max. No company, title, or signature block.                                                                                                                                                               | One short casual line: `Thanks,` then the sender's first name. No formal close.           |
| Punctuation         | Plain ASCII only: no em-dashes or en-dashes (use a hyphen `-`, a comma, or a new sentence), straight quotes only, no ellipsis character.                                                                                                                                                                                                                                             | Same rule.                                                                                |
| Reader calibration  | Apply `brief.reader_style.calibration_directive` to structure, length-bias, pacing, and which angle leads first (stay inside the word budget). When `reader_style.social_style` is null, lead with the angle fitting `role_priorities` and keep a neutral structure. Never name or allude to the inferred trait; the sender voice still owns the salutation, sign-off, and register. | Same rule.                                                                                |
| Markdown formatting | Plain prose. No headings, no bullets inside the body.                                                                                                                                                                                                                                                                                                                                | Plain prose. No markdown at all.                                                          |
| Self-promotion      | Not in paragraph 1. Paragraph 1 is about the recipient and the hook.                                                                                                                                                                                                                                                                                                                 | Same rule.                                                                                |

### 3.3 Dispatch template (one Agent call per brief)

Use `subagent_type: expert-copywriter`. Dispatch prompt:

```
Topic: Cold outreach <channel> letter to <recipient.name>, <recipient.title> at <company.name>.
Format: <channel>            # email | email_generic | linkedin_dm
Output path: <PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Source artifacts:
  - <PROJECT_ROOT>/.mz/task/<task_name>/briefs/<channel>_<contact_slug>.json
Audience: one named recipient (not a segment). Treat as cold - recipient has
  not heard from sender. Personalization is real and verifiable.
Value claim: <copy from brief.value_claim>
Sender voice: <copy verbatim from brief.sender_voice>
Greeting: open with ONE salutation line, then the hook on the next line.
  Voice-adaptive: "Hi <first_name>," (warm) / "Hello <first_name>," (neutral)
  / "Dear <title last_name>," (formal). For email_generic keep "Hi <first_name>,"
  when the recipient name is known, else "Hello,". For linkedin_dm always the
  casual "Hi <first_name>,". The salutation is NOT the opening hook - the first
  sentence after it must still carry the personalization hook.
Opening hook: pick exactly ONE item from brief.personalization_hooks (use
  the most specific, verifiable one - prefer items tagged source: deeper_intel
  when available) and reference it in the first sentence after the salutation.
  Do not invent.
Outreach angle: <copy from brief.chosen_angle>
Reader calibration: apply brief.reader_style.calibration_directive to the
  letter's structure, length-bias, pacing, and which angle leads first - stay
  inside the channel word budget. If brief.reader_style.social_style is null,
  lead with the angle that fits brief.reader_style.role_priorities and keep a
  neutral structure. This shapes HOW the letter reads only: never name, hint
  at, or flatter the inferred trait, and never change the salutation, sign-off,
  or voice register - the sender voice owns those (split by dimension).
Local climate (optional): if brief.climate_context is set, you may open on ONE
  angle from brief.climate_context.angles, but cite only climate facts that
  also appear in brief.verified_entities.
Sign-off: close with a voice-adaptive gratitude line, then the sender's first
  name on the next line. Map by sender voice: warm -> "Thanks,"; neutral ->
  "Best regards,"; formal -> "Sincerely,". At most one thank-you; do not
  over-thank. For linkedin_dm use a short "Thanks," then the first name -
  nothing formal.
Punctuation: plain ASCII only. Do NOT use em-dashes or en-dashes anywhere -
  use a hyphen "-", a comma, or split the sentence. Straight quotes only, no
  curly quotes, no ellipsis character.
Channel-specific constraints:
<copy the relevant channel column from the channel rules table verbatim>
Frontmatter requirement: emit the YAML block at the very top of the output
  file with no content above it. The block must contain `subject` (email only,
  <=55 chars, about 6-7 words), `channel`, and `recipient`. The naturalizer
  preserves the frontmatter automatically - the subject is safest inside it.
Evidence available (use as written - do NOT extend):
  - Verified entities: <list from brief.verified_entities>
  - Personalization signals: <list from brief.personalization_hooks>
  - Recent news with implications: <list from brief.card_recent_news>
Forbidden:
  - Any number, date, customer name, product name, or metric not in
    brief.verified_entities.
  - Generic OPENERS (the first sentence after the salutation, not the
    salutation itself, which is required): "I hope this finds you well",
    "I came across your profile", "I noticed your company", "Just reaching
    out", "I wanted to introduce".
  - Adjective stacks ("innovative, scalable, transformative").
  - Hyperbole ("revolutionary", "game-changing", "10x").
  - Decorative affirmatives ("Absolutely", "Certainly", "Indeed").
  - Em-dashes, en-dashes, curly quotes, or the ellipsis character anywhere in
    the letter. ASCII punctuation only.
  - Self-promotion in paragraph 1.
  - Naming, hinting at, or flattering the recipient's inferred personality or
    communication style. The reader calibration must stay invisible in the text.
  - Marketing-framework toolkit beyond Rule of One + one persuasion lever.
    This is short cold outreach, not a landing page.
Open questions / gaps: if brief.personalization_hooks contains zero items
  with `verified: true`, emit STATUS: BLOCKED - do not draft.
```

The brief file already carries `channel_format_rules` (a verbatim copy of the channel rules row); the dispatch above also embeds the rules to be safe.

### 3.4 Validate each draft

After every agent in a wave returns:

1. Verify the output file exists and is non-empty.
1. Verify `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`. On `BLOCKED` or `NEEDS_CONTEXT`, record the failure in `state.md` and continue with other drafts — do not auto-retry.
1. Verify the file starts with a YAML frontmatter block (`---` on line 1).
1. For `email` / `email_generic`: the frontmatter must contain a `subject:` key with \<=55 chars.
1. Verify the salutation and sign-off are present. Email/email_generic: a salutation line at the top of the body, and a sign-off of a gratitude close ("Thanks,"/"Best regards,"/"Sincerely,") followed by the sender's first name. linkedin_dm: a casual "Hi <first>," opener and a short "Thanks," + first-name close. Mark `failed_draft: missing_salutation` or `failed_draft: missing_signoff` if either is absent.
1. Verify body word count is within channel budget:
   - `email` / `email_generic`: 120-180 words (count body words only, excluding frontmatter, subject, the salutation line, and the sign-off lines).
   - `linkedin_dm`: 60-100 words (count body words only, excluding frontmatter, the salutation line, and the sign-off lines).
1. If any check fails for a particular draft, mark it `failed_draft` in `state.md`. Phase 5 will list it as `### Skipped: <Name>: <reason>` instead of including a letter.

Update `state.md`: Phase → `drafts_complete`, append a `Drafts` list (path per file, plus pass/fail flag).

## Error Handling within these phases

- `expert-copywriter` returns `BLOCKED` for a contact → record the contact as `failed_draft` in `state.md`; continue with other contacts; Phase 5 emits a `### Skipped` block for that contact; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry.
- `expert-copywriter` returns `NEEDS_CONTEXT` for a contact → treat the same as `BLOCKED` (the missing context is the agent's responsibility to surface in the final report; we will not re-dispatch automatically).
- `expert-copywriter` invents entities not in `brief.verified_entities` → Phase 3 validation catches it (entity check); mark `failed_draft: invented_entity`; continue.
