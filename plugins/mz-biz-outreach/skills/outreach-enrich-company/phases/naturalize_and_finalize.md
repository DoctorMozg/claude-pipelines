# Phase 4: Naturalize — Phase 5: Rewrite Card

Read `SKILL.md` first. This file picks up after either:

- **Phase 3 complete** (`drafts_complete`) — `enrich_mode` is `both` or `skip` (run Phase 4 → 5; drafting is in `<SKILL_DIR>/phases/draft_letters.md`).
- **Phase 2 complete** (`enrichment_complete`) — `enrich_mode` is `only` (skip Phase 4, run only Phase 5 with deeper intel).

## Phase 4: Naturalize pass (expert-naturalizer)

Skipped entirely when `enrich_mode == "only"`. Mandatory otherwise. Runs automatically. No approval gate.

### 4.1 Snapshot pre-naturalize state

For every draft that passed Phase 3 validation, copy it aside as a snapshot:

```bash
cp "<PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md" \
   "<PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md.pre-naturalize"
```

The snapshots are used to revert any draft that the naturalizer damages.

### 4.2 Dispatch plan

Dispatch one `expert-naturalizer` agent per surviving draft, in parallel waves of at most 6 concurrent agents per wave. Use `subagent_type: expert-naturalizer`.

Emit the pre-dispatch manifest right before each wave, and pass each role label as the agent's `description`. Skip both blocks for a wave of one agent:

```
Dispatching letter naturalization, wave <k> — <N> agents in parallel
Purpose: remove AI patterns from each surviving letter draft
- expert-naturalizer — email rewrite, contact <n>
- expert-naturalizer — LinkedIn DM rewrite, contact <n>
```

### 4.3 Dispatch template (one Agent call per draft)

```
Mode: in-place rewrite
Input file: <PROJECT_ROOT>/.mz/task/<task_name>/drafts/<channel>_<contact_slug>.md
Output file: same path - overwrite
Severity: Light
  (the copywriter just wrote this; AI-pattern density is bounded;
   this is short cold outreach, not generic long copy)
Strategy:
  - Vocabulary swaps only where an avoid-list term degrades trust
  - Remove all em-dashes and en-dashes - convert each to a hyphen, a comma, or
    a sentence break. Zero tolerance, not "reduce".
  - Strip curly quotes and the ellipsis character; output straight ASCII
    quotes and "..." only
  - Break mechanical antithesis if present
  - Restore natural contractions ("don't", "you're") where the tone allows
  - Do not cut sentences for length compliance - preserve length within +/-5%
  - Do not rebuild paragraph variance - short letters are 1-3 paragraphs
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
Format awareness: <email | email_generic | linkedin_dm> - do not introduce
  headings, bullet lists, or markdown decoration.
Medium routing override: "Email between colleagues" for email and
  email_generic; "Chat, DMs, comments, casual Markdown" for linkedin_dm.
  Plain ASCII punctuation in all channels.
```

### 4.4 Post-naturalize validation per draft

Once every agent of a wave has reported, failed or been stopped, emit that wave's post-wave rollup before validating:

```
Wave complete (letter naturalization, wave <k>) — <returned>/<dispatched> agents returned
- expert-naturalizer: <STATUS> — <summary, ≤8 words>
```

An agent that returns no valid final `STATUS:` line is listed as `<agent>: NO RETURN BLOCK` and counted as not returned.

After each naturalizer returns:

1. Read the rewritten draft.
1. Confirm the YAML frontmatter is intact and `subject:` (email) is unchanged from the pre-naturalize snapshot. If `subject:` drifted, revert the draft from the snapshot and mark `naturalize_reverted: subject_drift` in `state.md`.
1. Count body words (excluding frontmatter, subject, the salutation line, and the sign-off lines). If outside the channel budget by >5%, revert from snapshot and mark `naturalize_reverted: length_out_of_bounds`.
1. Confirm every entity from `brief.verified_entities` still appears in the body. If a verified entity was removed, revert and mark `naturalize_reverted: entity_dropped`.
1. Confirm the salutation and sign-off survived. If the naturalizer dropped the greeting or the closing, revert from snapshot and mark `naturalize_reverted: structure_dropped`.
1. Scan the body for AI-artifact punctuation: em-dashes and en-dashes (the `—` and `–` characters), curly quotes, and the ellipsis character. If any are found, re-dispatch the naturalizer ONCE with an instruction to replace each flagged character with grammatical ASCII (a hyphen, comma, period, straight quote, or "...") and change nothing else, then re-scan. If artifacts still remain, mark `naturalize_artifacts_remain` in `state.md` and downgrade the run STATUS to `DONE_WITH_CONCERNS` - never emit a letter that still contains them.

After processing all drafts, delete the `.pre-naturalize` snapshots:

```bash
rm "<PROJECT_ROOT>/.mz/task/<task_name>/drafts/"*.pre-naturalize
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

Read `<PROJECT_ROOT>/.mz/task/<task_name>/deeper_intelligence.md` (produced in Phase 2). Its content already contains the full `## Deeper Intelligence` heading + body + footer line; use it verbatim as `NEW_D_BLOCK`.

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
1. Compute `today = $(date +%Y-%m-%d)` and `target_path = <PROJECT_ROOT>/.mz/outreach/active/<today>_<company_slug>.md`.
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
  find "<PROJECT_ROOT>/.mz/outreach/active" -maxdepth 1 -type f \
    -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_<company_slug>.md' \
    ! -path "<target_path>" -delete 2>/dev/null
  ```

If the `rm` fails (permission, missing file), do not fail the run — log `relocation_cleanup_failed: <reason>` in `state.md` and downgrade the final STATUS to `DONE_WITH_CONCERNS`. The card content at `target_path` is canonical regardless.

Update `state.md`: Phase → `complete`, `Status: complete`, `phase_complete: true`, `what_remains: []`, set `CompletedAt: <ISO timestamp>`, record `LettersWritten: <count>`, `LettersSkipped: <count>`, `NaturalizeReverted: <count>`, `SubagentsDispatched: <count>`, `SubagentsFailed: <count>`, `LightQueries: <count>`, `TargetPath: <target_path>`, `SourceDeleted: <yes | no | failed:<reason>>`.

## Final output

Emit the verification block defined in `<SKILL_DIR>/references/verification-summary.md`.

## Error Handling within these phases

- `expert-naturalizer` returns `BLOCKED` for a draft → revert to the pre-naturalize snapshot; mark `naturalize_reverted: agent_blocked`; the pre-naturalize draft proceeds to Phase 5.
- `expert-naturalizer` returns `DONE_WITH_CONCERNS` → run the post-naturalize validation; revert if any check fails; otherwise accept the rewrite and surface the concerns in `state.md`.
- A draft's subject line drifts after naturalize → always revert (subject lines are the highest-stakes single field).
- All drafts fail naturalize → continue with the pre-naturalize drafts; the naturalize column in the card footer reports `reverted: <count>`.
- Card has no `*Generated:` footer → fall back to first-section-anchor split as defined in Phase 5.4; log the deviation; final STATUS becomes `DONE_WITH_CONCERNS`.
- `deeper_intelligence.md` missing while `enrich_mode in (both, only)` → emit the failure-surface placeholder section defined in Phase 5.3; downgrade STATUS to `DONE_WITH_CONCERNS`.
