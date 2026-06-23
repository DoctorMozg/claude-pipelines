# Phase 3: Draft Letters — Phase 4: Naturalize — Phase 5: Rewrite Card

Read `SKILL.md` first. This file picks up after either:

- **Phase 2 complete** (`enrichment_complete`) — `enrich_mode` is `both` (run drafting + card rewrite with both sections) or `only` (skip drafting/naturalize, run only Phase 5 with deeper intel).
- **Phase 1 complete** (`card_parsed`) — `enrich_mode` is `skip` (no Phase 2; run Phase 3 → 4 → 5 with letters only).

## Phase 3: Draft letters (expert-copywriter)

Skipped entirely when `enrich_mode == "only"`.

### 3.0 Build per-contact briefs

Brief-building moved out of Phase 1 (which now only parses the card and writes `card_parsed.json`). Read inputs:

1. `.mz/task/<task_name>/card_parsed.json` — written in Phase 1.
1. `.mz/task/<task_name>/enrichment/*.json` — written in Phase 2 (skip if `enrich_mode == "skip"`; the directory will be empty).
1. `.mz/task/<task_name>/deeper_intelligence.md` — written in Phase 2 (skip if `enrich_mode == "skip"`).
1. The orchestrator's in-memory light-pass results from Phase 1 (per-contact public-activity strings).
1. Sender voice + outreach angles resolved in Phase 1.

For each of the (up to 5) Key Contacts from `card_parsed.json`, decide the channel:

- If `channels_override == "email"` → channel = `email` (requires the contact's email to be known, else fall back to LinkedIn DM if URL known, else `skip`).
- If `channels_override == "linkedin"` → channel = `linkedin_dm` (requires LinkedIn URL, else `skip`).
- If `channels_override == "both"` → emit TWO briefs per contact when both handles exist: one `email`, one `linkedin_dm`. Skip a missing channel cleanly.
- If no override (default) → prefer `email` when an email is known; else `linkedin_dm` when LinkedIn URL is known; else `skip` and record the reason.

Per-channel handle resolution: the card lists contact emails in the `## Key Contacts` block's `**Emails**:` line — these are company-level (info@, sales@). Person-specific emails appear in the per-contact line only if the card found one. If only generic emails exist, mark the channel as `email_generic` and target the generic address with the contact named in the body.

For each non-skipped (contact, channel) pair, write `.mz/task/<task_name>/briefs/<channel>_<contact_slug>.json`:

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

For each brief whose `chosen_channel` is not `skip` (dedupe by contact — one profile per person even when both an email and a DM brief exist), dispatch one `outreach-personality-profiler`. Dispatch in parallel waves of at most 6 concurrent agents per wave; up to 5 contacts fit in one wave. Foreground only — do not background the profiler.

Output path per contact: `.mz/task/<task_name>/profiles/<contact_slug>.json`.

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
Output file: .mz/task/<task_name>/profiles/<contact_slug>.json

Assert a Social Style ONLY with at least one citable public-footprint cue. With no
citable cue, leave social_style null and populate role_priorities from the title.
Emit a calibration_directive that shapes structure, length-bias, pacing, and which
angle leads - never naming or alluding to the trait, never touching the salutation,
sign-off, or voice register. At most 3 web calls. Professional signal only.
```

After each profiler returns: read its `profiles/<contact_slug>.json` and merge `social_style`, `role_priorities`, `confidence`, `calibration_directive`, and `evidence` into the `reader_style` block of every brief for that contact (both channels if two exist). On `BLOCKED` / `NEEDS_CONTEXT`, leave that contact's `reader_style` as the null placeholder (the letter falls back to neutral structure) and record `profile_failed: <contact_slug>` in `state.md` — do not auto-retry, do not block the run.

Update `state.md`: append a `Profiles` list (one path per profiled contact with its `social_style`/`confidence` or `fallback:role_priorities`), and record `ProfilesFootprint` (count with a citable style) and `ProfilesRolePriority` (count that fell back).

### 3.1 Dispatch plan

Read every brief file under `.mz/task/<task_name>/briefs/`. For each brief whose `chosen_channel` is not `skip`, dispatch one `expert-copywriter` agent. Dispatch in parallel waves of at most 6 concurrent agents per wave. Wait for each wave to complete before starting the next. Do not background any agent — writer agents must run in the foreground.

Per-brief output path: `.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md` (use `<channel>_<contact_slug>` from the brief filename).

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
Output path: .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Source artifacts:
  - .mz/task/<task_name>/briefs/<channel>_<contact_slug>.json
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

## Phase 4: Naturalize pass (expert-naturalizer)

Skipped entirely when `enrich_mode == "only"`. Mandatory otherwise. Runs automatically. No approval gate.

### 4.1 Snapshot pre-naturalize state

For every draft that passed Phase 3 validation, copy it aside as a snapshot:

```bash
cp .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md \
   .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md.pre-naturalize
```

The snapshots are used to revert any draft that the naturalizer damages.

### 4.2 Dispatch plan

Dispatch one `expert-naturalizer` agent per surviving draft, in parallel waves of at most 6 concurrent agents per wave. Foreground only. Use `subagent_type: expert-naturalizer`.

### 4.3 Dispatch template (one Agent call per draft)

```
Mode: in-place rewrite
Input file: .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Output file: same path - overwrite
Severity: Light
  (the copywriter just wrote this; AI-pattern density is bounded;
   this is short cold outreach, not generic long copy)
Strategy:
  - Vocabulary swaps only where an avoid-list term degrades trust
  - Remove ALL em-dashes and en-dashes - convert each to a hyphen, a comma, or
    a sentence break. Zero tolerance, not "reduce".
  - Strip curly quotes and the ellipsis character; output straight ASCII
    quotes and "..." only
  - Break mechanical antithesis if present
  - Restore natural contractions ("don't", "you're") where the tone allows
  - Do NOT cut sentences for length compliance - preserve length within +/-5%
  - Do NOT rebuild paragraph variance - short letters are 1-3 paragraphs
Preserve list (immutable):
  - The YAML frontmatter block at the top of the file (auto-preserved)
  - The salutation line and the sign-off lines (gratitude close + sender first
    name) - keep both present; smooth wording only, never drop the greeting or
    the closing
  - Recipient's first name (first appearance and every appearance)
  - Company name, product names, and every proper noun from
    brief.verified_entities
  - Every number, date, metric, and URL - verbatim
  - The personalization-hook sentence (paragraph 1, the sentence containing
    the cited signal) - substance preserved; minor word swaps only if the
    cited entity stays untouched
  - The CTA sentence - verbatim
  - The reader-calibrated shape - do not reorder the paragraphs, re-expand a
    deliberately brief letter, or move the leading angle. Smooth wording only.
Word-count target: preserve length within +/-5%. Channel budget is the hard
  floor/ceiling, measured excluding the salutation and sign-off lines:
  - email / email_generic: body 120-180 words
  - linkedin_dm: 60-100 words
  If naturalization would push the count outside the budget, return the
  input unchanged with a note in the change report.
Long-document handling: N/A - input is 60-180 words.
Web research: no
Format awareness: <email | email_generic | linkedin_dm> - do NOT introduce
  headings, bullet lists, or markdown decoration.
Medium routing override: "Email between colleagues" for email and
  email_generic; "Chat, DMs, comments, casual Markdown" for linkedin_dm.
  Plain ASCII punctuation in all channels.
```

### 4.4 Post-naturalize validation per draft

After each naturalizer returns:

1. Read the rewritten draft.
1. Confirm the YAML frontmatter is intact and `subject:` (email) is unchanged from the pre-naturalize snapshot. If `subject:` drifted, revert the draft from the snapshot and mark `naturalize_reverted: subject_drift` in `state.md`.
1. Count body words (excluding frontmatter, subject, the salutation line, and the sign-off lines). If outside the channel budget by >5%, revert from snapshot and mark `naturalize_reverted: length_out_of_bounds`.
1. Confirm every entity from `brief.verified_entities` still appears in the body. If a verified entity was removed, revert and mark `naturalize_reverted: entity_dropped`.
1. Confirm the salutation and sign-off survived. If the naturalizer dropped the greeting or the closing, revert from snapshot and mark `naturalize_reverted: structure_dropped`.
1. Scan the body for AI-artifact punctuation: em-dashes and en-dashes (the `—` and `–` characters), curly quotes, and the ellipsis character. If any are found, re-dispatch the naturalizer ONCE with an instruction to replace each flagged character with grammatical ASCII (a hyphen, comma, period, straight quote, or "...") and change nothing else, then re-scan. If artifacts still remain, mark `naturalize_artifacts_remain` in `state.md` and downgrade the run STATUS to `DONE_WITH_CONCERNS` - never emit a letter that still contains them.

After processing all drafts, delete the `.pre-naturalize` snapshots:

```bash
rm .mz/task/<task_name>/drafts/*.pre-naturalize
```

Update `state.md`: Phase → `naturalize_complete`, append a `NaturalizeResults` list (one row per draft with `pass | reverted:<reason>`).

## Phase 5: Rewrite card

Always runs. Outputs depend on `enrich_mode`:

- `both` → both `## Deeper Intelligence` and `## Outreach Letters` replaced.
- `only` → `## Deeper Intelligence` replaced; any prior `## Outreach Letters` preserved verbatim.
- `skip` → `## Outreach Letters` replaced; any prior `## Deeper Intelligence` preserved verbatim.

### 5.1 Strip naturalization report from each draft

Only runs if Phase 4 ran (i.e., `enrich_mode != "only"`). The naturalizer always appends a footer of the shape:

```
---

## Naturalization report
...
```

For each surviving draft (passed Phase 4 or reverted from snapshot):

1. Read the draft file.
1. Find the trailing block matching `\n---\s*\n+## Naturalization report` and everything after it to end-of-file.
1. Write the file back without that block.
1. If no such block is found, leave the file untouched and log `naturalization report footer not found` in `state.md` (informational, not an error).

### 5.2 Assemble the `## Outreach Letters` section (NEW_L_BLOCK)

Skip if `enrich_mode == "only"`.

For every contact processed in Phase 3, in the order they appeared in the card's Key Contacts section, emit one block. Three block shapes:

**Letter block (email / email_generic):**

```markdown
### To <Name> (<Title>): Email

**To**: <recipient email or "<generic@domain> (cc: <Name>)" if email_generic>
**Subject**: <subject from draft frontmatter>

<body of the draft, with frontmatter stripped - it already opens with the salutation and ends with the gratitude sign-off plus sender first name>

*Reader calibration: <reader_style.social_style, or "role-priorities" when null> (<reader_style.confidence>) - <one-line basis: the cited evidence cue, or the role priorities the letter led with>*
```

**Letter block (linkedin_dm):**

```markdown
### To <Name> (<Title>): LinkedIn DM

**LinkedIn**: <linkedin_url>

<body of the draft, with frontmatter stripped>

*Reader calibration: <reader_style.social_style, or "role-priorities" when null> (<reader_style.confidence>) - <one-line basis: the cited evidence cue, or the role priorities the letter led with>*
```

**Skipped block (no channel or failed draft):**

```markdown
### Skipped: <Name> (<Title>)

**Reason**: <one line: "no contact route" | "copywriter blocked: <message>" | "naturalize reverted: <reason>" | "draft failed validation: <reason>">
```

Between blocks insert a `---` separator line. Omit the `*Reader calibration:*` line entirely when `personality_mode == "off"` (no profiling ran, so there is nothing to disclose).

Open the section with a heading and close it with a generated-line footer:

```markdown
## Outreach Letters

<block 1>

---

<block 2>

---

...

*Letters generated: <today's date> | naturalized: yes | light queries: <K> | reverted: <R>*
```

`<today's date>` uses ISO format (`YYYY-MM-DD`).

### 5.3 Assemble the `## Deeper Intelligence` section (NEW_D_BLOCK)

Skip if `enrich_mode == "skip"`.

Read `.mz/task/<task_name>/deeper_intelligence.md` (produced in Phase 2). Its content already contains the full `## Deeper Intelligence` heading + body + footer line; use it verbatim as `NEW_D_BLOCK`.

If the file is missing (Phase 2 was skipped or all subagents failed before writing it), emit a minimal placeholder so the user sees the failure surface:

```markdown
## Deeper Intelligence

*All enrichment subagents failed to produce artifacts. See state.md EnrichmentResults for details.*

*Deeper intelligence: <today's date> | subagents: 0 | failed: 5*
```

### 5.4 Rebuild card content and write to `target_path`

Card rewrite uses Read + Write to write the entire card file to its destination. This is idempotent on re-run — any prior `## Deeper Intelligence` and `## Outreach Letters` sections are replaced cleanly; `## Interaction History` is preserved verbatim.

1. Read the existing card file at `source_path` (set in Phase 0).
1. Locate the line beginning with `*Generated:` (the canonical card footer written by `outreach-card-writer`). It will be on its own line near the bottom of the original card content.
1. Detect three append-zone landmarks (each may be present or absent):
   - **D** — the existing `## Deeper Intelligence` heading (from a prior run of this skill).
   - **L** — the existing `## Outreach Letters` heading (from a prior run of this skill).
   - **H** — the existing `## Interaction History` heading (from `/outreach-update-card`).
1. Compute anchors and slices:
   - `HEAD` = content from the start through the `*Generated: ...*` line (inclusive). If no `*Generated:` line exists, `HEAD` = content up to the first of `D`, `L`, or `H` (whichever appears first), or the entire content if none are present.
   - `PRIOR_D_BLOCK` = if `D` found, content from the `## Deeper Intelligence` heading through the line immediately before the next of `L`, `H`, or EOF (whichever comes first). Else `""`.
   - `PRIOR_L_BLOCK` = if `L` found, content from the `## Outreach Letters` heading through the line immediately before `H` or EOF (whichever comes first). Else `""`.
   - `HIST` = if `H` found, content from the `## Interaction History` heading through EOF. Else `""`.
1. Resolve the final blocks per `enrich_mode`:
   - `enrich_mode == "both"` → `D_BLOCK = NEW_D_BLOCK`; `L_BLOCK = NEW_L_BLOCK`.
   - `enrich_mode == "only"` → `D_BLOCK = NEW_D_BLOCK`; `L_BLOCK = PRIOR_L_BLOCK` (preserve prior letters if any, else empty).
   - `enrich_mode == "skip"` → `D_BLOCK = PRIOR_D_BLOCK` (preserve prior deeper intel if any, else empty); `L_BLOCK = NEW_L_BLOCK`.
1. Compose the rebuilt content. Join non-empty blocks with `\n\n` separators in this order: `HEAD`, `D_BLOCK`, `L_BLOCK`, `HIST`. Drop any block that is the empty string. Ensure the file ends with exactly one trailing newline.
1. Compute `today = $(date +%Y-%m-%d)` and `target_path = .mz/outreach/active/<today>_<company_slug>.md`.
1. Write the rebuilt content to `target_path`.

If the card has no `*Generated:` footer (hand-authored card that does not follow the canonical shape) and the canonical headers were still found in Phase 0, the `HEAD` falls back to content-up-to-first-section-anchor as defined above. Log this in `state.md`.

### 5.5 Relocate: delete the source file

After `target_path` is written and its contents verified by re-reading:

- If `source_path == target_path` (re-run on the same active card with same date), skip cleanup.
- If `source_path != target_path`, the card has moved from a research-baseline path or a stale active path. Remove the old file:
  ```bash
  rm "<source_path>"
  ```
- Defensive sweep — remove any other stale active files for this slug that are not the target:
  ```bash
  find .mz/outreach/active -maxdepth 1 -type f \
    -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<company_slug>.md' \
    ! -path "<target_path>" -delete 2>/dev/null
  ```

If the `rm` fails (permission, missing file), do NOT fail the run — log `relocation_cleanup_failed: <reason>` in `state.md` and downgrade the final STATUS to `DONE_WITH_CONCERNS`. The card content at `target_path` is canonical regardless.

Update `state.md`: Phase → `complete`, set `CompletedAt: <ISO timestamp>`, record `LettersWritten: <count>`, `LettersSkipped: <count>`, `NaturalizeReverted: <count>`, `SubagentsDispatched: <count>`, `SubagentsFailed: <count>`, `LightQueries: <count>`, `TargetPath: <target_path>`, `SourceDeleted: <yes | no | failed:<reason>>`.

## Final output

Emit the verification block defined in `SKILL.md` § Phase 6.

## Error Handling within these phases

- `expert-copywriter` returns `BLOCKED` for a contact → record the contact as `failed_draft` in `state.md`; continue with other contacts; Phase 5 emits a `### Skipped` block for that contact; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry.
- `expert-copywriter` returns `NEEDS_CONTEXT` for a contact → treat the same as `BLOCKED` (the missing context is the agent's responsibility to surface in the final report; we will not re-dispatch automatically).
- `expert-copywriter` invents entities not in `brief.verified_entities` → Phase 3 validation catches it (entity check); mark `failed_draft: invented_entity`; continue.
- `expert-naturalizer` returns `BLOCKED` for a draft → revert to the pre-naturalize snapshot; mark `naturalize_reverted: agent_blocked`; the pre-naturalize draft proceeds to Phase 5.
- `expert-naturalizer` returns `DONE_WITH_CONCERNS` → run the post-naturalize validation; revert if any check fails; otherwise accept the rewrite and surface the concerns in `state.md`.
- A draft's subject line drifts after naturalize → always revert (subject lines are the highest-stakes single field).
- All drafts fail naturalize → continue with the pre-naturalize drafts; the naturalize column in the card footer reports `reverted: <count>`.
- Card has no `*Generated:` footer → fall back to first-section-anchor split as defined in Phase 5.4; log the deviation; final STATUS becomes `DONE_WITH_CONCERNS`.
- `deeper_intelligence.md` missing while `enrich_mode in (both, only)` → emit the failure-surface placeholder section defined in Phase 5.3; downgrade STATUS to `DONE_WITH_CONCERNS`.
