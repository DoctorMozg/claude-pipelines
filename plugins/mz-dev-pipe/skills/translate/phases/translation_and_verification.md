# Phases 2-7: Translation + Tiered Verification + Finalization

Full detail for the translation, consistency, multi-tier verification, bounded re-translation, and finalization phases of the `translate` skill. `SKILL.md` reads this file on entry to Phase 2 and keeps it loaded until Phase 7 completes. Tier-1 structural checks fire inside every translator dispatch; Tier-2 LLM-as-Judge reviews every produced chunk; Tier-3 uncertainty-driven deep verification spends budget only on chunks the earlier tiers flagged as risky.

## Contents

- [Phase 2: Parallel Translation Waves + Tier-1 Verification](#phase-2-parallel-translation-waves--tier-1-verification)
- [Phase 3: Cross-File Consistency + Glossary Delta Merge](#phase-3-cross-file-consistency--glossary-delta-merge)
- [Phase 4: Tier-2 Semantic Verification (LLM-as-Judge)](#phase-4-tier-2-semantic-verification-llm-as-judge)
- [Phase 5: Tier-3 Uncertainty-Driven Deep Verification](#phase-5-tier-3-uncertainty-driven-deep-verification)
- [Phase 6: Bounded Re-Translation Loop](#phase-6-bounded-re-translation-loop)
- [Phase 7: Finalization](#phase-7-finalization)

______________________________________________________________________

## Phase 2: Parallel Translation Waves + Tier-1 Verification

**Goal**: translate every unit in `<task_dir>/translation_plan.md` with `pipeline-translator` agents running in parallel waves, each agent verifying its own output via Tier-1 structural checks before returning.

### 2.1 Wave Construction

Read `<task_dir>/translation_plan.md` and parse the file list table into **translation units** (one per file under `MAX_CHUNK_LINES`, one per chunk for split files). Each unit carries its stable `chunk_id` from the plan.

Group units into waves of size ≤ `MAX_PARALLEL_TRANSLATORS`, ordered **smallest chunks first** — front-loads fast failures so placeholder/glossary problems surface before long-form chunks burn budget. Persist the wave assignment to `<task_dir>/wave_schedule.md` so re-entry after context compaction does not re-shuffle the order.

State stays at `plan_approved` until the first wave dispatch fires.

### 2.2 Wave Dispatch Loop

For each wave, dispatch all N translator agents in a **single orchestrator message** as parallel tool calls (Rule 13). Never sequentialize dispatches within a wave. Phrase each dispatch as a short, task-specific block (Rule 9) — the agent already knows its own process, rules, and output format.

Wave-sizing: `MAX_PARALLEL_TRANSLATORS` is the hard upper bound. With 14 units and `MAX_PARALLEL_TRANSLATORS = 6`, the schedule is `[6, 6, 2]` — three sequential waves, each a single parallel message. Do not reshuffle mid-run; the smallest-chunks-first order from 2.1 is the execution order.

Each dispatch description contains only:

- `task_dir` (absolute path), unit spec (source path + optional `chunk_range` + `chunk_id`), `source_lang` / `target_lang` (ISO 639-1), `output_path`, `output_mode`.
- `glossary_path` pointer (read-only) and a one-line reminder to emit the glossary delta to `<task_dir>/glossary_delta_<chunk_id>.json`.
- Grep pointers at the reference files, not inline content: `Grep references/placeholder-patterns.md for the framework section and Combined Regex`, and `Grep references/markdown-preservation-rules.md for the element type you need (e.g. rg -A5 'fenced code')`.
- `mode: translate`.
- One explicit line: `run Tier-1 structural verification and emit the confidence report to <task_dir>/confidence_<chunk_id>.json before returning`.

Example dispatch shape (fill task-specific fields per unit):

```text
task_dir: /home/.../.mz/task/translate_docs_143022
unit: docs/guide.md chunk_id=guide_md_h2_install lines 42-118
source_lang: en  target_lang: ru
output_path: docs/guide.ru.md  output_mode: sidecar
glossary_path: <task_dir>/glossary.json (read-only; emit delta to glossary_delta_<chunk_id>.json)
mode: translate
references: grep references/placeholder-patterns.md and references/markdown-preservation-rules.md
Required: run Tier-1 and emit confidence_<chunk_id>.json before returning.
```

The example contains no copy of the agent's process sections, no inline placeholder regex, no rubric restatement, no severity-label reminder — `pipeline-translator.md` already defines those (Rule 9). The dispatch is context and pointers, nothing else.

Collect every response from the wave. Parse the terminal `STATUS:` line per dispatch (Rule 21):

- **`DONE`** — record the output file path, confidence report path, and glossary delta path into `<task_dir>/wave_results.md`. Advance the chunk into Phase 3 eligibility.
- **`DONE_WITH_CONCERNS`** — append the agent's `## Concerns` block to `<task_dir>/concerns.md` under a heading for this `chunk_id`. Still advance the chunk — Tier-2 may judge the concern harmless. Do not treat `DONE_WITH_CONCERNS` as a failure.
- **`NEEDS_CONTEXT`** — re-dispatch **once** with the agent's `## Required Context` block resolved in the new prompt (e.g. missing glossary entry, ambiguous output path). The re-dispatch counts against `MAX_VERIFICATION_ATTEMPTS` for that chunk. If the re-dispatch also returns `NEEDS_CONTEXT`, escalate via AskUserQuestion.
- **`BLOCKED`** — **never auto-retry**. Escalate immediately via AskUserQuestion, pasting the agent's `## Blocker` section verbatim. Halt the wave until the user responds.

Worked example for a 4-dispatch wave: three `DONE`, one `DONE_WITH_CONCERNS` (two untranslated idioms). Record all four paths in `wave_results.md`, append the concerns block to `concerns.md` under the chunk id, advance all four to Phase 3. Do not stop the pipeline — Tier-2 may still accept, Phase 6 retries on `Critical:`.

After the last wave finishes, update `state.md` Phase → `translation_complete`.

______________________________________________________________________

## Phase 3: Cross-File Consistency + Glossary Delta Merge

**Goal**: merge all glossary deltas into the canonical glossary once, then sweep for cross-file term divergence and re-dispatch translators on any chunks that drifted.

### 3.1 Glossary Delta Merge

Run this step **exactly once**, after the last Phase-2 wave completes — not per-wave. Per-wave merging adds file-contention risk for no benefit.

Read every `<task_dir>/glossary_delta_<chunk_id>.json` listed in `wave_results.md`. Merge into `<task_dir>/glossary.json` with a **first-wins** policy per source term: earliest delta wins unless a later delta reports a strictly higher frequency, in which case the later delta wins. Record every conflict (same source term, different target translation) in `<task_dir>/glossary_conflicts.md` with chunk ids, both candidates, and the winner — consumed by the Phase 7 summary.

Worked example: chunk A emits `{"deployment": {"ru": "развёртывание", "frequency": 4}}`; chunk B emits `{"deployment": {"ru": "деплой", "frequency": 7}}`. Chunk A is read first (alphabetical). First-wins picks `развёртывание`, but chunk B's strictly higher frequency flips the decision to `деплой`. Both candidates logged.

### 3.2 Consistency Scan

For every glossary term whose frequency is greater than 3 (lower-frequency terms produce too much noise to be worth a scan), run a Bash-level grep count on both sides of the translation:

```bash
rg -c -F '<source_term>' <source_files>
rg -c -F '<target_translation>' <output_files>
```

If `target_count < 0.8 * source_count`, the term has drifted. Record term, counts, and affected output chunks in `<task_dir>/consistency_flags.md`. Flagged chunks move to Phase 3.3; terms passing the threshold need no action.

Worked example: glossary maps `deployment` → `развёртывание`. Source contains 12 occurrences, output 8 → `0.66`, below the 0.8 floor. Grep each output file for `развёртывание` to find covered chunks, subtract from the total to find the drifted ones. Flag only the missing chunks.

Terms with frequency ≤ 3 are excluded: drift on tiny counts is statistical noise and the 80% threshold is meaningless. The Phase 7 summary surfaces these as low-frequency entries for human review.

### 3.3 Targeted Re-Translation

For each flagged chunk, re-dispatch `pipeline-translator` in `mode: translate` with a task-specific prompt (Rule 9) naming the divergent terms, their required target translations from the merged glossary, and the output file to rewrite. Include the standard reminder to run Tier-1 and emit a fresh confidence report. Re-dispatches count against `MAX_VERIFICATION_ATTEMPTS` per chunk. Group into waves of ≤ `MAX_PARALLEL_TRANSLATORS`, emit each wave in a single parallel message. Status handling follows the four-status protocol from Phase 2.2.

Update `state.md` Phase → `consistency_complete`.

______________________________________________________________________

## Phase 4: Tier-2 Semantic Verification (LLM-as-Judge)

**Goal**: run an LLM-as-Judge review over every produced chunk with priority-ordered review targets, wave-split to keep individual reviewer contexts tractable on large jobs.

### 4.1 Judge Wave-Split

Compute `judge_batches = ceil(total_chunks / MAX_JUDGE_BATCH)`. If `judge_batches == 1`, dispatch a single `pipeline-code-reviewer`. Otherwise dispatch `judge_batches` reviewers as parallel tool calls in one orchestrator message (Rule 13). Never sequentialize — parallel dispatch + finding merge is the only way to avoid context blowup on long jobs.

Group chunks into batches by shared source file when possible so a reviewer can cross-reference neighboring sections. Break ties by chunk order from `wave_results.md`.

### 4.2 Reviewer Dispatch Prompt

One short, task-specific description block per reviewer (Rule 9). Each block names only:

- The batch's source chunks + translated chunks + `glossary.json` + the per-chunk confidence reports from Phase 2.
- Priority-ordered review targets: **(a)** headings and section titles, **(b)** sentences containing glossary terms, **(c)** sentences containing placeholders, **(d)** first paragraph of each major section, **(e)** the rest of the prose. Review in that order; spend budget on (a)-(d) first.
- The translation rubric: meaning preservation, terminology adherence to glossary, placeholder parity, structural fidelity, and natural phrasing in the target language.
- Severity label requirements (Rule 20): every finding must be prefixed with `Critical:`, `Nit:`, `Optional:`, or `FYI:`. `VERDICT: PASS` only when zero `Critical:` findings exist.
- Request for concise output — output tokens cost 5x input.

Example dispatch shape:

```text
task_dir: /home/.../.mz/task/translate_docs_143022
batch: 1 of 2  chunks: guide_md_h2_install, guide_md_h2_config, api_md_h2_endpoints
source files: docs/guide.md, docs/api.md (read relevant line ranges per chunk)
translated files: docs/guide.ru.md, docs/api.ru.md
glossary: <task_dir>/glossary.json
confidence reports: <task_dir>/confidence_<chunk_id>.json (one per chunk)
priority: (a) headings, (b) glossary-term sentences, (c) placeholder sentences, (d) first paragraph per section, (e) rest
rubric: meaning, glossary adherence, placeholder parity, structural fidelity, naturalness
severity: Critical: / Nit: / Optional: / FYI:
verdict: PASS only if zero Critical. Concise output.
```

Status handling follows the four-status protocol (Rule 21): `DONE` = normal; `DONE_WITH_CONCERNS` (operational issues, e.g. unreadable chunk) → `<task_dir>/concerns.md`; `NEEDS_CONTEXT` → one re-dispatch with missing files attached; `BLOCKED` → escalate via AskUserQuestion, halt Phase 4.

### 4.3 Finding Merge

Concatenate every reviewer's output into `<task_dir>/tier2_findings.md`, grouped by `chunk_id`. Any chunk with a `Critical:` prefix is marked for back-translation in Phase 5.3 and re-translation in Phase 6. Chunks with only `Nit:` / `Optional:` / `FYI:` findings are Tier-2 PASS and do not advance to Phase 6, but their `FYI:` lines flow into the Phase 7 summary.

`tier2_findings.md` shape:

```text
## chunk_id: guide_md_h2_install
VERDICT: PASS
- Nit: heading "Installation" translated with trailing period; remove.
- FYI: paragraph 3 uses a longer compound noun than source but meaning preserved.

## chunk_id: troubleshoot_md_h2_errors
VERDICT: FAIL
- Critical: glossary term "rollback" rendered as "откат" in most sentences but as "возврат" in paragraph 2.
- Nit: bullet list uses en-dash while source uses hyphen.
```

The canonical marker is the `VERDICT:` line — grep it to enumerate failing chunks. Phases 5 and 6 use this file as their input.

Update `state.md` Phase → `judge_complete`.

______________________________________________________________________

## Phase 5: Tier-3 Uncertainty-Driven Deep Verification

**Goal**: spend deep-verification budget only on chunks that earned it. Cheap chunks that cleared Tier-1 and Tier-2 cleanly do **not** enter Tier-3 — this is the entire point of the uncertainty-driven design.

**Inputs**: per-chunk confidence reports written in Phase 2 + Tier-2 findings written in Phase 4.

**Chunk selection rule**: a chunk enters Tier-3 if **any** of the following is true:

- `overall_confidence` is `medium` or `low` in its confidence report.
- `uncertain_spans` contains at least one entry.
- Its Tier-2 finding set contains at least one `Critical:` entry.

A chunk that has `overall_confidence: high`, empty `uncertain_spans`, and zero `Critical:` findings skips Phase 5 entirely. Record the skipped-chunk count for the Phase 7 summary.

### 5.1 Wiktionary Term Lookup

For every `uncertain_spans` entry whose `span` is a single word (no whitespace), dispatch a WebFetch call:

```text
https://en.wiktionary.org/w/api.php?action=query&titles=<target_term>&prop=revisions&rvprop=content&format=json
```

Extract the target-language sense if present. Global cap: `MAX_WIKTIONARY_LOOKUPS`. Track running count in `<task_dir>/tier3_ledger.md`; once the cap is hit, record `Cap reached` and stop. Non-existence on Wiktionary is an `FYI:`, not a blocking finding — absence of an entry does not mean the translation is wrong.

Worked example: `uncertain_spans` has `"idempotent"` and `"распределённая система"`. The first is single-word — call Wiktionary with `titles=идемпотентный` (translated form on disk) and parse the revisions content for a Russian sense. If no page, log `FYI: 'идемпотентный' not found on Wiktionary`. The multi-word span is skipped for Wiktionary (multi-word entries are unreliable) and remains eligible for Phase 5.2 MyMemory spot-checking.

### 5.2 MyMemory Spot-Check

Select up to 3 uncertain-span sentences across the whole job, prioritized by Tier-2 severity. Call:

```text
https://api.mymemory.translated.net/get?q=<sentence>&langpair=<src>|<tgt>&de=<placeholder_email>
```

via WebFetch. Compare against the LLM translation for the same sentence. Flag only **hard content mismatches** (meaning diverges, not phrasing). Paraphrase differences are expected and must not be flagged. Global cap: `MAX_MYMEMORY_QUERIES` per run (keeps us comfortably under MyMemory's 5000-character/day free tier). Record every query, result, and outcome in `<task_dir>/tier3_ledger.md`.

Selection algorithm: sort Tier-3-eligible chunks by severity (`Critical:` first, `uncertain_spans` only second); within each bucket pick the longest uncertain span first; take the top 3. Spends budget on the most operationally important sentences.

Hard-mismatch rule: different **subjects** or different **action verbs** → `Critical:`. Word order, article usage, tense, or synonym differences → no finding. When in doubt, lean toward no finding; the Phase 7 `Recommended Next Steps` block is the safety net.

### 5.3 Back-Translation

Run back-translation **only** on chunks whose Tier-2 finding set contains at least one `Critical:` entry. This is the most expensive Tier-3 probe; gate it strictly.

Dispatch `pipeline-translator` with `mode: back_translate` and a task-specific prompt (Rule 9) containing only:

- The already-translated chunk content.
- The reversed language pair (`source_lang` becomes the target, original `target_lang` becomes the source).
- An explicit line: `mode: back_translate — plain text only, no glossary, no structural checks, no confidence report`.

Batch the back-translation dispatches for a single Phase-5 pass into a **single orchestrator message** as parallel tool calls when more than one chunk needs it (Rule 13), bounded by `MAX_PARALLEL_TRANSLATORS`.

Collect each response (the agent returns plain back-translated text inline). Compute similarity against the original source chunk:

```bash
python3 -c "import difflib,sys; print(difflib.SequenceMatcher(None, sys.argv[1], sys.argv[2]).ratio())" "<orig>" "<back>"
```

If `python3` is unavailable, fall back to a pure-awk Jaccard word-set intersection: lowercase and tokenize both texts, compute `|intersection| / |union|` via `awk`. Both paths produce a scalar in `[0, 1]`.

Thresholds:

- **`ratio < 0.3`** — STRONG FAILURE. Log `Critical:` and queue for Phase 6. The diff algorithm cannot align the round-trip with the original — translation lost meaning or introduced new content.
- **`0.3 ≤ ratio ≤ 0.7`** — AMBIGUOUS. Log `FYI:` for human review; does **not** trigger Phase 6 on its own. Paraphrase band: word order/choice shifted enough to score moderately distant, but meaning usually intact. Auto-retranslation here would thrash.
- **`ratio > 0.7`** — acceptable. No new finding.

Examples: `"Deploy the service to production"` → `"Deploy service to the production environment"` scores ~0.72, no finding. `"Roll back the last migration"` → `"Cancel last operation"` scores ~0.35, `FYI:`. `"Enable two-factor authentication"` → `"Turn off the device"` scores ~0.18, `Critical:` queued for Phase 6.

Tier-3 findings (Wiktionary, MyMemory, back-translation) are appended to `<task_dir>/tier2_findings.md` under their chunk headings so Phase 6 sees one unified finding stream per chunk. Update `state.md` Phase → `deep_verify_complete`.

______________________________________________________________________

## Phase 6: Bounded Re-Translation Loop

**Goal**: re-translate every chunk that still has an unresolved `Critical:` finding after Tiers 1-3, with a deterministic termination bound.

For each chunk whose merged finding set (Tier-2 + Tier-3) contains at least one `Critical:` entry, re-dispatch `pipeline-translator` in `mode: translate` with a task-specific prompt (Rule 9) that contains only:

- The unit spec (source path + `chunk_range` + `chunk_id`) and the existing `output_path`.
- The exact `Critical:` findings for this chunk, verbatim from `tier2_findings.md`.
- A one-line instruction: `re-translate the affected spans targeting these findings, preserve all structural elements, run Tier-1 verification, and emit a fresh confidence report before returning`.

Emit all Phase-6 dispatches for a single iteration in a **single orchestrator message** as parallel tool calls, bounded by `MAX_PARALLEL_TRANSLATORS`. Apply the four-status protocol exactly as in Phase 2.2 (`DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`).

Every Phase-6 re-dispatch counts against `MAX_VERIFICATION_ATTEMPTS` for its chunk. Once a chunk hits the cap, stop re-dispatching it: keep the current translation on disk, write a `DONE_WITH_CONCERNS` entry into `<task_dir>/concerns.md` listing the unresolved findings, and let it flow into the Phase 7 summary.

Attempt-counter accounting is **global per chunk across all phases** — Phase 2.2 initial dispatches, Phase 2.2 `NEEDS_CONTEXT` re-dispatches, Phase 3.3 consistency-driven re-dispatches, and Phase 6 finding-driven re-dispatches all debit the same counter. Once a chunk exhausts `MAX_VERIFICATION_ATTEMPTS`, the next Phase 6 candidacy converts directly to a `DONE_WITH_CONCERNS` summary entry without another dispatch. Track per-chunk counts in `<task_dir>/wave_results.md`.

After a successful re-translation, the affected chunk **re-runs Tier-1 only**. Tier-2 and Tier-3 do **not** re-run on retried chunks — re-running Tier-2 would risk new `Critical:` findings and non-termination. The loop runs at most `MAX_VERIFICATION_ATTEMPTS` times per chunk and always terminates.

Update `state.md` Phase → `retranslation_complete`.

______________________________________________________________________

## Phase 7: Finalization

**Goal**: write the run summary, update state, and report to the user.

### 7.1 Summary Writeback

Write `<task_dir>/summary.md` with the following sections, in order:

- **Files translated** — source path → output path map, one row per unit.
- **Per-chunk confidence** — `chunk_id`, `overall_confidence`, count of `uncertain_spans` (from the Phase 2 confidence reports).
- **Tier-1 pass/fail** — one row per chunk: verification checks that passed, any that failed on the first attempt and required retry.
- **Tier-2 verdict** — per-chunk `VERDICT: PASS` / `FAIL`, the batch count (`judge_batches`), and the total finding count grouped by severity (`Critical:` / `Nit:` / `Optional:` / `FYI:`).
- **Tier-3 lookups used** — running counts pulled from `<task_dir>/tier3_ledger.md`: Wiktionary calls (`<used> / MAX_WIKTIONARY_LOOKUPS`), MyMemory queries (`<used> / MAX_MYMEMORY_QUERIES`), back-translation dispatches, similarity scores.
- **Phase 6 re-translation count** — total re-dispatches, count of chunks that hit `MAX_VERIFICATION_ATTEMPTS`.
- **Glossary counts** — seeded terms (from Phase 1.6), added terms (merged from deltas in Phase 3.1), conflict count (from `glossary_conflicts.md`).
- **Concerns** — every entry from `<task_dir>/concerns.md`, grouped by chunk, so `DONE_WITH_CONCERNS` items are visible up front.
- **Recommended next steps** — human-review priorities (ambiguous similarity ranges, residual Tier-2 FYIs, unresolved glossary conflicts).

Full `summary.md` shape:

```text
# Translation Summary — translate_docs_143022

Language pair: en → ru
Files translated: 4 sources → 4 outputs (sidecar mode)
Total chunks: 11

## Files
docs/guide.md → docs/guide.ru.md
docs/api.md   → docs/api.ru.md
README.md     → README.ru.md

## Per-Chunk Confidence
guide_md_h2_install       high    uncertain_spans=0
troubleshoot_md_h2_errors low     uncertain_spans=4

## Tier-1 Structural
11/11 passed on first attempt. 0 retries.

## Tier-2 Judge
judge_batches: 2 (MAX_JUDGE_BATCH)
verdicts: 10 PASS / 1 FAIL (troubleshoot_md_h2_errors)
findings: Critical=1  Nit=3  Optional=2  FYI=5

## Tier-3 Deep Verification
eligible chunks: 3 of 11  (8 skipped — high confidence, zero Critical)
Wiktionary: 6 / MAX_WIKTIONARY_LOOKUPS
MyMemory:   2 / MAX_MYMEMORY_QUERIES
Back-translation: 1 chunk (ratio 0.24 — STRONG FAILURE, queued for Phase 6)

## Phase 6 Re-Translation
re-dispatches: 1
cap hits: 0
final status: 11/11 DONE

## Glossary
seeded: 15  added: 4  conflicts: 1 (deployment → "развёртывание" wins over "деплой")

## Concerns
(none)

## Recommended Next Steps
- Human review on troubleshoot_md_h2_errors (one Tier-3 AMBIGUOUS FYI).
- Review the deployment/деплой glossary conflict against house style.
```

Tier-3 counters are always expressed as `<used> / MAX_*` so the reader sees consumption and cap in one line. The `cap hits` row is the key operational signal: non-zero means chunks exited with unresolved `Critical:` findings and need human attention.

### 7.2 State Update

Set `state.md` Phase → `complete`. Record the following fields in the final state block:

- `ended_at` — current wall-clock time.
- `final_outputs` — every output path written across Phases 2, 3.3, and 6.
- `escalations` — every AskUserQuestion prompt, `BLOCKED` halt, and `DONE_WITH_CONCERNS` chunk.
- `phase_history` — ordered list of transitions (`plan_approved` → `translation_complete` → `consistency_complete` → `judge_complete` → `deep_verify_complete` → `retranslation_complete` → `complete`).
- `tier3_ledger_path` — pointer to `<task_dir>/tier3_ledger.md` for API-usage audits.

`state.md` is the single source of truth for pipeline re-entry after context compaction. Always re-read on re-entry; never rely on in-memory conversation state.

### 7.3 User Report

Print the Phase 7.1 summary block to the user in the orchestrator's final message. Do not delegate this step — it is the terminal user-visible output for the skill. Keep formatting identical to the written `summary.md` so the on-disk artifact and the chat output agree byte-for-byte.
