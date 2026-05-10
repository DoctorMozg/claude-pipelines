# Phases 1-1.5: Discovery, Planning, User Approval

Full detail for the discovery and planning phases of the translate skill plus the approval gate that precedes any translator dispatch. The orchestrator (`SKILL.md`) reads this file on phase entry and never pre-loads it. Every concrete bound referenced here (`MAX_CHUNK_LINES`, `MAX_PARALLEL_TRANSLATORS`, `MAX_APPROVAL_ITERATIONS`, `MAX_JUDGE_BATCH`, `MAX_WIKTIONARY_LOOKUPS`, `MAX_MYMEMORY_QUERIES`) is defined once in `SKILL.md` and referenced by name only.

## Contents

- [Phase 1: Discovery](#phase-1-discovery)
  - 1.1 Parse Intent
  - 1.2 File Discovery
  - 1.3 Source Language Detection
  - 1.4 Target Language Normalization
  - 1.5 Output Path Resolution
  - 1.6 Glossary Seeding
  - 1.7 Chunking Strategy
  - 1.8 Plan Artifact
- [Phase 1.5: User Approval Gate](#phase-15-user-approval-gate)

______________________________________________________________________

## Phase 1: Discovery

**Goal**: Turn the raw user request into a concrete, reviewable translation plan — with files, languages, output paths, a seeded glossary, and a chunk layout — without dispatching a single translator.

### 1.1 Parse Intent

You parse `$ARGUMENTS` into four fields:

- **target language** — required. An ISO 639-1 two-letter code, a BCP 47 tag, a human name (English or native), or an ISO 639-2/3 code. Normalization happens in 1.4.
- **source language** — optional. Same accepted forms as target. When omitted, run auto-detection in 1.3.
- **file tokens / globs** — required. One or more file paths or glob patterns.
- **output mode** — optional. One of `sidecar` (default when omitted), `inplace`, or `i18n`. Expressed as `mode:<value>`.

**Accepted input forms**:

| Raw argument                                        | target | source      | files             | mode      |
| --------------------------------------------------- | ------ | ----------- | ----------------- | --------- |
| `translate README.md to ru`                         | `ru`   | auto-detect | `README.md`       | `sidecar` |
| `translate locales/en.json to fr mode:i18n`         | `fr`   | `en` (path) | `locales/en.json` | `i18n`    |
| `translate docs/**/*.md to Japanese`                | `ja`   | auto-detect | `docs/**/*.md`    | `sidecar` |
| `translate from en to de CHANGELOG.md mode:inplace` | `de`   | `en`        | `CHANGELOG.md`    | `inplace` |

Empty or ambiguous arguments are never guessed. On any of the following, escalate via `AskUserQuestion`:

- No target language supplied.
- No file tokens supplied.
- Target language token fails the anti-injection allow-list in `references/language-codes.md`.
- Two or more candidate output modes named in the same argument.

No verification opt-in flag exists in the grammar — verification is always on (Tier-1 structural, Tier-2 judge, Tier-3 uncertainty-driven). The approval gate in 1.5 presents its fixed cost; do not offer an opt-out.

Persist the parse result to `state.md` before moving to 1.2:

```
phase: parse_intent_complete
raw_target: Japanese
raw_source: null
file_tokens: ["docs/**/*.md"]
output_mode: sidecar
```

Raw tokens stay in state after normalization as an audit trail — the approval gate surfaces them alongside canonical forms so the user can catch normalization mistakes.

### 1.2 File Discovery

You dispatch one `pipeline-researcher` agent (model: **sonnet**) to expand globs, detect formats, and produce a tabular inventory. The dispatch prompt is task-specific only and instructs the researcher to:

- Glob-expand every file token supplied in 1.1 against the worktree.
- For each resolved file, detect the format using extension first, then a `file` probe, then the first line (YAML frontmatter `---`, JSON `{`, `<?xml`). Supported formats: `md`, `mdx`, `json`, `yaml`, `yml`, `po`, `properties`, `strings`, `xliff`, `txt`.
- Record byte size and translatable-line count per file. Translatable lines means prose lines for markdown, value-side lines for JSON/YAML, `msgstr` for PO.
- Flag and exclude any file that looks binary, is a lockfile (`*.lock`, `*-lock.json`, `*.sum`), lives under a vendored or generated directory (`node_modules/`, `vendor/`, `dist/`, `build/`, `target/`, `.venv/`), or was produced by a code generator (header comment matches `(?i)generated|do not edit`).
- Return one concise table per report: path, format, size bytes, translatable lines, include-or-skip flag with reason.
- **Discovery only — no translation, no rewriting, no side-effecting writes.**

Dispatch model: `sonnet`. One researcher is enough — breadth scan, not deep read. Persist the researcher output at `<task_dir>/discovery.md` verbatim for 1.8. Request concise tabular output — the plan artifact only needs the table.

Expected shape of the researcher report (what the orchestrator parses back):

```
| path                       | format | bytes | lines | include | reason             |
| -------------------------- | ------ | ----- | ----- | ------- | ------------------ |
| README.md                  | md     | 4120  | 132   | yes     | primary doc        |
| docs/guide/setup.md        | md     | 8844  | 241   | yes     | primary doc        |
| node_modules/foo/README.md | md     | 1022  | 48    | no      | vendored directory |
| package-lock.json          | json   | 98210 | 3210  | no      | lockfile           |
```

If the researcher reports zero matching files, or every matching file is skipped (vendored/generated/binary), escalate via `AskUserQuestion` with the raw glob, search root, and skip reasons. Never silently broaden the glob.

### 1.3 Source Language Detection

Run only when 1.1 did not supply an explicit source. The tier order is fall-through with a 5-second budget per tier and a global minimum-input guard.

1. **LibreTranslate `/detect`** — `WebFetch` the configured mirror with the first 500 characters of the largest discovered file. 5-second timeout. Accept if the response confidence is ≥ 0.6 and the detected code is in the canonical set.
1. **Unicode script heuristic** — grep `references/language-codes.md` for the `## Script → Language Fallback Heuristic` table, count code points in the first 500 characters of the sample per range, and pick the majority. Reference: grep `references/language-codes.md` for `## Script → Language Fallback Heuristic`.
1. **One-shot haiku agent** — dispatch a single haiku-model `pipeline-researcher` with the 500-char sample and the prompt "What ISO 639-1 language code is this? Reply with a single two-letter code only." Accept if the reply is in the canonical set.
1. **AskUserQuestion** — escalate with the first line of the sample and the list of discovered files; never guess past this point.

**Minimum input guard**: if the concatenated sample across discovered files is fewer than 20 characters, skip all four tiers and escalate immediately via `AskUserQuestion` — short strings carry too little signal for any heuristic to be reliable. Reference: grep `references/language-codes.md` for `Minimum input length`.

Persist to `state.md`: `source_lang` and `source_lang_method` (`libretranslate` / `script_heuristic` / `haiku_agent` / `user`). The method is audit-only; the approval gate echoes it so the user can see how detection landed.

Example fall-through for a mixed-content file:

```
tier 1 libretranslate: timeout after 5s                  → fall through
tier 2 script heuristic: 340 Latin chars, ambiguous      → fall through
tier 3 haiku agent: "en"                                 → accept
state.md source_lang: en, source_lang_method: haiku_agent
```

Early stop: if tier 1 returns ≥ 0.9 confidence and the detected code is in the canonical set, skip tiers 2–4. Reference: grep `references/language-codes.md` for `Early stop on high confidence`.

### 1.4 Target Language Normalization

Normalize the raw target token from 1.1 into the canonical ISO 639-1 two-letter form. Reference: grep `references/language-codes.md` for `## Normalization Table`. The grep should return one to five rows; if it returns zero, the token is unmapped.

Validation sequence (fail closed on the first failure):

1. Anti-injection allow-list (`^[A-Za-z0-9_-]+$`) on the raw input.
1. Length cap ≤ 32 characters on the raw input.
1. Grep the normalization table for the raw input (case-insensitive).
1. If the user supplied a BCP 47 tag with a region or script subtag (`zh-Hans`, `pt-BR`, `sr-Latn`), store the original tag in a separate `target_variant` field alongside the canonical `target_lang`. The canonical code drives every downstream call; the variant is a translator hint only.
1. Reject identical source and target after normalization.

On any failure, write `LANG_UNKNOWN: <raw input>` to `state.md` under `last_error` and escalate via `AskUserQuestion` with the raw token and a pointer to the reference file. Never silently substitute a nearby code.

Persist `target_lang` (and `target_variant` when present) to `state.md`.

### 1.5 Output Path Resolution

Resolve one output path per discovered file based on the parsed output mode:

- **`sidecar`** (default). Sibling file with target code injected before the extension. `README.md` → `README.<tgt>.md`. Does not touch the source file. Safe default for documentation repos.
- **`inplace`**. Only when the raw arguments contained literal `mode:inplace`. Output path equals source path — source gets overwritten. Append `INPLACE_DESTRUCTIVE` to the plan artifact in 1.8 so the approval gate surfaces it. Never infer; require the literal flag.
- **`i18n`**. Rewrite the `locales/<lang>/…` or `i18n/<lang>/…` segment with the target code. `locales/en/common.json` → `locales/<tgt>/common.json`. If no recognizable segment exists, fall back to `sidecar` for that file and append an `FYI:` warning to the plan. Do not escalate.

Concrete examples:

| Source path                  | Mode      | Target | Output path               | Note                             |
| ---------------------------- | --------- | ------ | ------------------------- | -------------------------------- |
| `README.md`                  | `sidecar` | `ru`   | `README.ru.md`            | default                          |
| `docs/guide/setup.md`        | `sidecar` | `ja`   | `docs/guide/setup.ja.md`  | default                          |
| `CHANGELOG.md`               | `inplace` | `de`   | `CHANGELOG.md`            | `INPLACE_DESTRUCTIVE`            |
| `locales/en/common.json`     | `i18n`    | `fr`   | `locales/fr/common.json`  | rewrote `en` segment             |
| `src/i18n/en-US/buttons.yml` | `i18n`    | `es`   | `src/i18n/es/buttons.yml` | rewrote `en-US` segment          |
| `content/post-001.mdx`       | `i18n`    | `zh`   | `content/post-001.zh.mdx` | no `locales/` → sidecar + `FYI:` |

Collision rule: if a resolved output path already exists and the mode is not `inplace`, flag the file with `FILE_EXISTS` in the plan — the approval gate surfaces it. Never silently overwrite.

Directory creation: for any `i18n` output whose target directory does not yet exist, do not create it during discovery. The translator agent creates parent directories at write time. Record as `CREATE_DIR` in the plan.

Mode parsing: `mode:INPLACE` normalizes case-insensitively to `inplace`. `mode:sidecars` or other typos escalate via `AskUserQuestion`. `mode:` with no value and two-mode arguments are rejected in 1.1.

Per-file persistence: one row per discovered file to `state.md` under `files[]` with `source_path`, `output_path`, `mode`, `flags` (semicolon-joined warnings). Later phases read from this table.

### 1.6 Glossary Seeding

Glossary seeding runs as two sequential `pipeline-researcher` dispatches (model: **sonnet**) — extraction is delegated so the orchestrator context stays small.

**Step 1 — term extraction.** Dispatch a researcher to scan all source files and extract candidate terms: capitalized multi-word phrases (product names, proper nouns), domain terms occurring more than twice, acronyms 2–6 characters. Record frequency plus one example sentence per term (taken from source, not invented). Cap at 30 entries, keep highest frequency on overflow.

**Step 2 — target rendering.** Dispatch a second researcher with the top 15 candidates plus source/target languages. Ask for a plausible translation per term with a one-line rationale. Leave acronyms and brand names untranslated, marked in the `notes` field.

Merge both outputs into `<task_dir>/glossary.json`. Schema: flat array of `{source_term, target_term, frequency, example_sentence, notes}`. Empty `target_term` means "keep verbatim". Write once in discovery — translator dispatches treat the file as read-only, per-chunk updates go into `glossary_delta_<chunk_id>.json` files merged in Phase 3.

Example seeded entry shape:

```json
{
  "source_term": "OAuth",
  "target_term": "",
  "frequency": 14,
  "example_sentence": "Set up OAuth 2.0 with the provider of your choice.",
  "notes": "acronym, keep verbatim"
}
```

If step 1 returns fewer than three candidates, skip step 2 and write `{"terms": []}`. The translator agent handles an empty glossary gracefully.

### 1.7 Chunking Strategy

Files with more lines than `MAX_CHUNK_LINES` are split into chunks. Splitting happens at structural boundaries, never at arbitrary line offsets — an LLM translating a half-paragraph or half-object produces visible seams.

- **Markdown / MDX** — split at top-level (`##`) heading boundaries. Each chunk starts at one `##` and runs until the next. Preserve the file's frontmatter block with the first chunk only.
- **JSON** — split at top-level key groups. Each chunk is a contiguous subtree of top-level keys (e.g., `auth`, `billing`, `settings`). Never split inside a nested object.
- **YAML / YML** — same rule as JSON: top-level key groups, no nested splits.
- **PO / XLIFF / .strings / .properties** — split at message-unit boundaries (every `msgid`/`msgstr` pair stays in one chunk). Never split inside a message unit.
- **Plain text** — split at blank-line paragraph boundaries, never mid-paragraph.

Each chunk gets a stable `chunk_id`. Markdown: `<basename>_chunk_<N>`. JSON/YAML i18n: `<basename>_<section>`. This id is the primary key for every Tier-1/2/3 artifact and must be stable across reruns. Small files under `MAX_CHUNK_LINES` become a single chunk `<basename>_chunk_0`.

Concrete example — a 620-line `README.md` with `MAX_CHUNK_LINES = 200` and four top-level `##` sections:

```
README.md (620 lines)
├── frontmatter + intro      → README_chunk_0 (lines 1–80)
├── ## Installation          → README_chunk_1 (lines 81–220)
├── ## Usage                 → README_chunk_2 (lines 221–410)
└── ## API Reference         → README_chunk_3 (lines 411–620)
```

Concrete example — a flat `locales/en/common.json` with three top-level key groups:

```
locales/en/common.json (840 lines)
├── "auth": { … }            → en_common_auth
├── "billing": { … }         → en_common_billing
└── "settings": { … }        → en_common_settings
```

When a top-level section is itself longer than `MAX_CHUNK_LINES`, split further at `###` boundaries with a composite id (`README_chunk_api_reference_0`, …). Never fall back to line-number slicing — a half-paragraph chunk breaks Tier-2 judge review.

Persist the chunk table to `state.md` under `chunks[]` with fields `chunk_id`, `source_path`, `start_line`, `end_line`, `section_title`. The Phase 2 wave builder reads from this table.

### 1.8 Plan Artifact

Write `<task_dir>/translation_plan.md` with the fields below. This is the single document the approval gate in 1.5 shows to the user; it must be readable top-to-bottom without opening any other file.

- **Source language** — canonical ISO 639-1 code plus native name (Reference: grep `references/language-codes.md` for `Native-Name Reference`).
- **Target language** — canonical ISO 639-1 code plus native name plus `target_variant` if the user supplied one.
- **Output mode** — `sidecar` / `inplace` / `i18n`. When the mode is `inplace`, append the `INPLACE_DESTRUCTIVE` warning in bold on its own line.
- **File list table** — one row per file: `path → output_path → format → translatable lines → chunk count`. Append per-row flags (`FILE_EXISTS`, `FALLBACK_SIDECAR`, `INPLACE_DESTRUCTIVE`) in the rightmost column.
- **Seeded glossary summary** — count of terms, count of terms with a proposed target rendering, count of terms flagged as untranslatable (acronyms, brand names). Link to `<task_dir>/glossary.json`.
- **Verification cost block** (see 1.5 below for the exact lines). Computed from the final chunk count.
- **Wave plan** — `ceil(total_chunks / MAX_PARALLEL_TRANSLATORS)` waves; list how many chunks fall into each wave. Prioritize smallest chunks first so fast failures surface early.

Example rendered plan excerpt (the shape the approval gate actually shows):

```markdown
# Translation Plan

- Source language: en (English)
- Target language: ja (日本語)
- Output mode: sidecar
- Seeded glossary: 22 terms (14 rendered, 6 brand/acronym, 2 pending)

## Files

| path                 | output_path             | format | lines | chunks | flags        |
| -------------------- | ----------------------- | ------ | ----- | ------ | ------------ |
| README.md            | README.ja.md            | md     | 620   | 4      |              |
| docs/guide/setup.md  | docs/guide/setup.ja.md  | md     | 241   | 2      |              |
| docs/legacy/old.md   | docs/legacy/old.ja.md   | md     | 88    | 1      | FILE_EXISTS  |

## Verification Cost

- Total translator chunks: 7
- Tier-2 judge dispatches: ceil(7 / MAX_JUDGE_BATCH) parallel calls
- Expected Tier-3: ≤ MAX_WIKTIONARY_LOOKUPS Wiktionary, ≤ MAX_MYMEMORY_QUERIES MyMemory
- Back-translation only on Tier-2 Critical findings
- Estimated wall-clock: 2–4 minutes
- verification is always on; no opt-in flag

## Wave Plan
- Wave 1 (MAX_PARALLEL_TRANSLATORS): smallest 6 chunks
- Wave 2: remaining 1 chunk
```

After writing the plan, update `state.md`: set `phase` to `discovery_complete`, write the chunk count into `total_chunks`, and write the computed wave count into `wave_count`. The approval gate in 1.5 reads both fields from state, not from memory.

Example `state.md` transition after 1.8 completes:

```
phase: discovery_complete
source_lang: en
target_lang: ja
target_variant: null
output_mode: sidecar
total_chunks: 7
wave_count: 2
discovery_report: discovery.md
plan_artifact: translation_plan.md
glossary: glossary.json
approval_iterations: 0
```

______________________________________________________________________

## Phase 1.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

**Goal**: explicit user approval for the plan and its fixed verification cost before any translator dispatches run. No chunk enters Phase 2 without an `approve` reply in this loop.

**Presentation**. Show the full contents of `<task_dir>/translation_plan.md` followed by the verification cost block (written inline in 1.8). Each bullet is one line, values plugged in from discovery:

- `Total translator chunks: <N>` — taken from `state.md` field `total_chunks`.
- `Tier-2 judge dispatches: ceil(N / MAX_JUDGE_BATCH) parallel calls` — one parallel judge wave per batch.
- `Expected Tier-3 lookups assuming ~20% of chunks flagged uncertain: up to MAX_WIKTIONARY_LOOKUPS Wiktionary calls and up to MAX_MYMEMORY_QUERIES MyMemory queries across the whole run`.
- `Back-translation dispatched only on chunks with a Tier-2 Critical: finding` — so the back-translation cost is bounded by Tier-2 severity, not by chunk count.
- `Estimated wall-clock range (wave count × ~30s + judge batches × ~20s + Tier-3 overhead)` — render as a range, not a point estimate.
- `Output paths and mode (with INPLACE_DESTRUCTIVE highlighted if applicable)` — echo the plan's file list flag column so the user sees destructive writes up front.
- `verification is always on; no opt-in flag`.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Translation Plan Ready for Review**

You are about to approve (or request changes to) the complete translation plan. The plan specifies which files will be translated, the target language, output mode, seeded glossary, and the full cost of verification (Tier-1 structural, Tier-2 judge, Tier-3 uncertainty-driven).

- **Approve** → proceed to Phase 2 (translator wave dispatch)
- **Reject** → task marked aborted, no files written
- **Feedback** → re-run discovery and planning steps incorporating your input, loop back here
```

**AskUserQuestion prompt**. Present the plan and cost block in the question body. The prompt ends literally with:

```
Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

Do not shorten, rephrase, or add trailing text — the literal string is what the response-handling bullets match against.

**Response handling**. Parse the reply into exactly one branch:

- **"approve"** → state `plan_approved`, record `approved_at` timestamp, proceed to Phase 2.
- **"reject"** → state `aborted_by_user`, write a one-line termination note to `state.md`, return control to the user. Do not dispatch anything.
- **Feedback** → incorporate (drop/add files, change mode, edit glossary, rename paths, change chunking), re-run affected sub-steps (typically 1.2, 1.5, 1.6, 1.7, 1.8 — 1.1 and 1.4 only re-run if the user changes the language or argument shape), overwrite the plan, return to this gate and re-present **via AskUserQuestion**. **This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.** Increment `approval_iterations` on every re-present. Bounded by `MAX_APPROVAL_ITERATIONS`; past that bound, escalate via `AskUserQuestion` with the last three feedback messages so the user can abort or give targeted guidance.

Each iteration re-presents the full plan and cost block — never diff-only, never summary-only. Context compaction may have destroyed the user's memory of earlier iterations.

**Feedback parsing**. Parse literal `approve` (case-insensitive, trimmed) as approval. Parse literal `reject` / `abort` / `cancel` / `stop` (case-insensitive, trimmed) as rejection. Everything else is feedback. A conditional approval ("I approve if you drop the README") is feedback with conditions — do NOT auto-advance; re-present after applying them.

**Feedback examples and the expected orchestrator action**:

- "Drop `docs/legacy/`" → remove matching files from discovery, re-run 1.5 (output path), 1.7 (chunking), 1.8 (plan), re-present.
- "Use `mode:inplace`" → change output_mode to `inplace`, re-run 1.5, add `INPLACE_DESTRUCTIVE` flag to every file, re-run 1.8, re-present. Surface the destructive warning prominently.
- "Glossary is missing `Auth Service`" → append the term to `glossary.json` with a researcher-suggested target, re-run 1.6 (merge), re-run 1.8, re-present.
- "Target should be `zh-Hant` not `zh`" → re-run 1.4, store `target_variant: zh-Hant`, re-run 1.8, re-present. Do not re-run discovery.
- "Split `README_chunk_2` further" → lower the effective `MAX_CHUNK_LINES` for that one file or add `###` splits, re-run 1.7 and 1.8, re-present.

**Iteration accounting**. Read `approval_iterations` before every re-present and compare to `MAX_APPROVAL_ITERATIONS`. Past the cap, escalate via `AskUserQuestion` with the last three feedback messages and three choices: `(a)` abort the task → `aborted_by_user`; `(b)` approve as-is → `plan_approved`, proceed; `(c)` one final narrow revision → apply, reset `approval_iterations` to 0, resume the normal loop. Never silently loop past the cap.

Persist the final outcome: `phase: plan_approved`, `approved_at`, `approval_iterations`. Phase 2 reads these as entry precondition — it refuses to dispatch if `phase != plan_approved`.
