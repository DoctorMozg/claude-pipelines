# Phase 2: Draft Letters — Phase 3: Naturalize — Phase 4: Append to Card

Read `SKILL.md` first. This file picks up after Phase 1 (briefs written under `.mz/task/<task_name>/briefs/`) and runs Phases 2 through 4.

## Phase 2: Draft letters (expert-copywriter)

### 2.1 Dispatch plan

Read every brief file under `.mz/task/<task_name>/briefs/`. For each brief whose `chosen_channel` is not `skip`, dispatch one `expert-copywriter` agent. Dispatch in parallel waves of at most 6 concurrent agents per wave. Wait for each wave to complete before starting the next. Do not background any agent — writer agents must run in the foreground.

Per-brief output path: `.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md` (use `<channel>_<contact_slug>` from the brief filename).

### 2.2 Channel rules table

Pass these constraints verbatim inside the dispatch so the agent does not improvise structure:

| Field               | `email` / `email_generic`                                                                             | `linkedin_dm`                                                                              |
| ------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Frontmatter         | YAML block at top with `subject`, `channel: email` (or `email_generic`), `recipient: <full name>`     | YAML block at top with `channel: linkedin_dm`, `recipient: <full name>` — no `subject` key |
| Body length         | 120–180 words                                                                                         | 60–100 words                                                                               |
| Subject line        | First field in the frontmatter. ≤55 chars. Specific verb + named outcome. No clickbait, no emoji.     | None (LinkedIn DMs have no subject field)                                                  |
| Opening sentence    | References exactly ONE personalization hook from `brief.personalization_hooks[*]`, verbatim or near.  | Same rule.                                                                                 |
| CTA                 | One imperative sentence near the end. One ask, low friction (15-min call, reply Y/N, share thoughts). | Same rule.                                                                                 |
| Sign-off            | One short line, sender's first name only. No company, no title, no signature block.                   | None.                                                                                      |
| Markdown formatting | Plain prose. No headings, no bullets inside the body.                                                 | Plain prose. No markdown at all.                                                           |
| Self-promotion      | Not in paragraph 1. Paragraph 1 is about the recipient and the hook.                                  | Same rule.                                                                                 |

### 2.3 Dispatch template (one Agent call per brief)

Use `subagent_type: expert-copywriter`. Dispatch prompt:

```
Topic: Cold outreach <channel> letter to <recipient.name>, <recipient.title> at <company.name>.
Format: <channel>            # email | email_generic | linkedin_dm
Output path: .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Source artifacts:
  - .mz/task/<task_name>/briefs/<channel>_<contact_slug>.json
Audience: one named recipient (not a segment). Treat as cold — recipient has
  not heard from sender. Personalization is real and verifiable.
Value claim: <copy from brief.value_claim>
Sender voice: <copy verbatim from brief.sender_voice>
Opening hook: pick exactly ONE item from brief.personalization_hooks (use
  the most specific, verifiable one) and reference it in the first sentence.
  Do not invent.
Outreach angle: <copy from brief.chosen_angle>
Channel-specific constraints:
<copy the relevant channel column from the channel rules table verbatim>
Frontmatter requirement: emit the YAML block at the very top of the output
  file with no content above it. The block must contain `subject` (email only,
  ≤55 chars), `channel`, and `recipient`. The naturalizer will preserve the
  frontmatter automatically — the subject is safest inside it.
Evidence available (use as written — do NOT extend):
  - Verified entities: <list from brief.verified_entities>
  - Personalization signals: <list from brief.personalization_hooks>
  - Recent news with implications: <list from brief.card_recent_news>
Forbidden:
  - Any number, date, customer name, product name, or metric not in
    brief.verified_entities.
  - Generic openers: "I hope this finds you well", "I came across your
    profile", "I noticed your company", "Just reaching out", "I wanted to
    introduce".
  - Adjective stacks ("innovative, scalable, transformative").
  - Hyperbole ("revolutionary", "game-changing", "10x").
  - Decorative affirmatives ("Absolutely", "Certainly", "Indeed").
  - Self-promotion in paragraph 1.
  - Marketing-framework toolkit beyond Rule of One + one persuasion lever.
    This is short cold outreach, not a landing page.
Open questions / gaps: if brief.personalization_hooks contains zero items
  with `verified: true`, emit STATUS: BLOCKED — do not draft.
```

The brief file already carries `channel_format_rules` (a verbatim copy of the channel rules row); the dispatch above also embeds the rules to be safe.

### 2.4 Validate each draft

After every agent in a wave returns:

1. Verify the output file exists and is non-empty.
1. Verify `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`. On `BLOCKED` or `NEEDS_CONTEXT`, record the failure in `state.md` and continue with other drafts — do not auto-retry.
1. Verify the file starts with a YAML frontmatter block (`---` on line 1).
1. For `email` / `email_generic`: the frontmatter must contain a `subject:` key with ≤55 chars.
1. Verify body word count is within channel budget:
   - `email` / `email_generic`: 120–180 words (count words in body only, excluding frontmatter, subject, sign-off line).
   - `linkedin_dm`: 60–100 words (count words in body only, excluding frontmatter).
1. If any check fails for a particular draft, mark it `failed_draft` in `state.md`. Phase 4 will list it as `### Skipped: <Name> — <reason>` instead of including a letter.

Update `state.md`: Phase → `drafts_complete`, append a `Drafts` list (path per file, plus pass/fail flag).

## Phase 3: Naturalize pass (expert-naturalizer)

Mandatory. Runs automatically. No approval gate.

### 3.1 Snapshot pre-naturalize state

For every draft that passed Phase 2 validation, copy it aside as a snapshot:

```bash
cp .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md \
   .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md.pre-naturalize
```

The snapshots are used to revert any draft that the naturalizer damages.

### 3.2 Dispatch plan

Dispatch one `expert-naturalizer` agent per surviving draft, in parallel waves of at most 6 concurrent agents per wave. Foreground only. Use `subagent_type: expert-naturalizer`.

### 3.3 Dispatch template (one Agent call per draft)

```
Mode: in-place rewrite
Input file: .mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Output file: same path — overwrite
Severity: Light
  (the copywriter just wrote this; AI-pattern density is bounded;
   this is short cold outreach, not generic long copy)
Strategy:
  - Vocabulary swaps only where an avoid-list term degrades trust
  - Em-dash reduction (keep ≤1 per letter)
  - Break mechanical antithesis if present
  - Restore natural contractions ("don't", "you're") where the tone allows
  - Do NOT cut sentences for length compliance — preserve length within ±5%
  - Do NOT rebuild paragraph variance — short letters are 1–3 paragraphs
Preserve list (immutable):
  - The YAML frontmatter block at the top of the file (auto-preserved)
  - Recipient's first name (first appearance and every appearance)
  - Sender's first name (sign-off line on email)
  - Company name, product names, and every proper noun from
    brief.verified_entities
  - Every number, date, metric, and URL — verbatim
  - The personalization-hook sentence (paragraph 1, the sentence containing
    the cited signal) — substance preserved; minor word swaps only if the
    cited entity stays untouched
  - The CTA sentence — verbatim
Word-count target: preserve length within ±5%. Channel budget is the hard
  floor/ceiling:
  - email / email_generic: body 120–180 words
  - linkedin_dm: 60–100 words
  If naturalization would push the count outside the budget, return the
  input unchanged with a note in the change report.
Long-document handling: N/A — input is 60–180 words.
Web research: no
Format awareness: <email | email_generic | linkedin_dm> — do NOT introduce
  headings, bullet lists, or markdown decoration.
Medium routing override: "Email between colleagues" for email and
  email_generic; "Chat, DMs, comments, casual Markdown" for linkedin_dm.
  Plain ASCII punctuation in all channels.
```

### 3.4 Post-naturalize validation per draft

After each naturalizer returns:

1. Read the rewritten draft.
1. Confirm the YAML frontmatter is intact and `subject:` (email) is unchanged from the pre-naturalize snapshot. If `subject:` drifted, revert the draft from the snapshot and mark `naturalize_reverted: subject_drift` in `state.md`.
1. Count body words (excluding frontmatter, subject, sign-off line). If outside the channel budget by >5%, revert from snapshot and mark `naturalize_reverted: length_out_of_bounds`.
1. Confirm every entity from `brief.verified_entities` still appears in the body. If a verified entity was removed, revert and mark `naturalize_reverted: entity_dropped`.

After processing all drafts, delete the `.pre-naturalize` snapshots:

```bash
rm .mz/task/<task_name>/drafts/*.pre-naturalize
```

Update `state.md`: Phase → `naturalize_complete`, append a `NaturalizeResults` list (one row per draft with `pass | reverted:<reason>`).

## Phase 4: Append to card

### 4.1 Strip naturalization report from each draft

The naturalizer always appends a footer of the shape:

```
---

## Naturalization report
...
```

For each surviving draft (passed Phase 3 or reverted from snapshot):

1. Read the draft file.
1. Find the trailing block matching `\n---\s*\n+## Naturalization report` and everything after it to end-of-file.
1. Write the file back without that block.
1. If no such block is found, leave the file untouched and log `naturalization report footer not found` in `state.md` (informational, not an error).

### 4.2 Assemble the `## Outreach Letters` section

For every contact processed in Phase 1, in the order they appeared in the card's Key Contacts section, emit one block. Three block shapes:

**Letter block (email / email_generic):**

```markdown
### To <Name> (<Title>) — Email

**To**: <recipient email or "<generic@domain> (cc: <Name>)" if email_generic>
**Subject**: <subject from draft frontmatter>

<body of the draft, with frontmatter stripped>

— <Sender first name from brief.sender_voice or "Sender">
```

**Letter block (linkedin_dm):**

```markdown
### To <Name> (<Title>) — LinkedIn DM

**LinkedIn**: <linkedin_url>

<body of the draft, with frontmatter stripped>
```

**Skipped block (no channel or failed draft):**

```markdown
### Skipped: <Name> (<Title>)

**Reason**: <one line — "no contact route" | "copywriter blocked: <message>" | "naturalize reverted: <reason>" | "draft failed validation: <reason>">
```

Between blocks insert a `---` separator line.

Open the section with a heading and close it with a generated-line footer:

```markdown
## Outreach Letters

<block 1>

---

<block 2>

---

...

*Letters generated: <today's date> | naturalized: yes | enrichment queries: <N> | reverted: <R>*
```

`<today's date>` uses ISO format (`YYYY-MM-DD`).

### 4.3 Rebuild card content and write to `target_path`

Card append uses Read + Write to write the entire card file to its destination. This is idempotent on re-run — any prior `## Outreach Letters` section is replaced cleanly.

1. Read the existing card file at `source_path` (set in Phase 0).
1. Locate the line beginning with `*Generated:` (the canonical card footer written by `outreach-card-writer`). It will be on its own line near the bottom.
1. Detect the two append-zone landmarks (each may be present or absent):
   - **L** — the existing `## Outreach Letters` heading (from a prior run of this skill).
   - **H** — the existing `## Interaction History` heading (from `/outreach-update-card`).
1. Compose the rebuilt content. Anchors used: `<HEAD>` = the card content up to and including the `*Generated: ...*` line; `<HIST>` = the `## Interaction History` heading and every line below it (or empty string if **H** is absent). Four cases:
   - **L absent, H absent** → `<HEAD>` + `\n\n` + `<new section>`
   - **L absent, H present** → `<HEAD>` + `\n\n` + `<new section>` + `\n\n` + `<HIST>`
   - **L present, H absent** → `<HEAD>` + `\n\n` + `<new section>` (discard everything between L and end-of-file)
   - **L present, H present** → `<HEAD>` + `\n\n` + `<new section>` + `\n\n` + `<HIST>` (discard everything between L and H; preserve H and below verbatim)
1. Compute `today = $(date +%Y-%m-%d)` and `target_path = .mz/outreach/active/<today>_<company_slug>.md`.
1. Write the rebuilt content to `target_path`. The `*Generated: ...*` line stays where it was; the new section (with its own `*Letters generated: ...*` footer) sits below it; `## Interaction History` (if any) is preserved verbatim at the bottom.

If the card has no `*Generated:` footer (hand-authored card that does not follow the canonical shape) and the canonical headers were still found in Phase 0, append the new section at the very end of the file as a fallback. Log this in `state.md`.

### 4.4 Relocate: delete the source file

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

Update `state.md`: Phase → `complete`, set `CompletedAt: <ISO timestamp>`, record `LettersWritten: <count>`, `LettersSkipped: <count>`, `NaturalizeReverted: <count>`, `EnrichmentQueries: <count>`, `TargetPath: <target_path>`, `SourceDeleted: <yes | no | failed:<reason>>`.

## Final output

Emit the verification block defined in `SKILL.md` § Phase 5.

## Error Handling within these phases

- `expert-copywriter` returns `BLOCKED` for a contact → record the contact as `failed_draft` in `state.md`; continue with other contacts; Phase 4 emits a `### Skipped` block for that contact; final STATUS becomes `DONE_WITH_CONCERNS`. Do not auto-retry.
- `expert-copywriter` returns `NEEDS_CONTEXT` for a contact → treat the same as `BLOCKED` (the missing context is the agent's responsibility to surface in the final report; we will not re-dispatch automatically).
- `expert-copywriter` invents entities not in `brief.verified_entities` → Phase 2 validation catches it (entity check); mark `failed_draft: invented_entity`; continue.
- `expert-naturalizer` returns `BLOCKED` for a draft → revert to the pre-naturalize snapshot; mark `naturalize_reverted: agent_blocked`; the pre-naturalize draft proceeds to Phase 4.
- `expert-naturalizer` returns `DONE_WITH_CONCERNS` → run the post-naturalize validation; revert if any check fails; otherwise accept the rewrite and surface the concerns in `state.md`.
- A draft's subject line drifts after naturalize → always revert (subject lines are the highest-stakes single field).
- All drafts fail naturalize → continue with the pre-naturalize drafts; the naturalize column in the card footer reports `reverted: <count>`.
- Card has no `*Generated:` footer → append the new section at end-of-file as a fallback (see Phase 4.3); log the deviation; final STATUS becomes `DONE_WITH_CONCERNS`.
