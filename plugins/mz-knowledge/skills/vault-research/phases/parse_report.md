# Phase 1: Parse Report and Filter Noise

## Goal

Split the resolved report into H2-delimited sections, classify each section as `noise` or `content` based on the `NOISE_SECTIONS` list, partition the retained content into sequential atomization windows bounded by `ATOMIZATION_WAVE_WORD_CAP`, and write `parsed_report.md` for the Phase 1.5 approval gate.

No vault writes happen in this phase. The only outputs are files under `TASK_DIR<task_name>/` and an updated `state.md`.

## Preconditions

Phase 0 has resolved `ReportPath`, `Vault`, and `PermanentFolder` in `state.md`. `TASK_DIR<task_name>/` exists on disk.

Constants used from `SKILL.md`:

- `NOISE_SECTIONS`: default pre-known noise headings (case-insensitive substring match).
- `ATOMIZATION_WAVE_WORD_CAP`: 450 words per atomization window.
- `LONG_REPORT_THRESHOLD_WORDS`: 2000 (already warned in Phase 0 if exceeded).
- `TASK_DIR`: `.mz/task/`.

## Step 1: Split the report into H2 sections

1. Use the `Read` tool on the report path from `state.md` (`ReportPath`). For reports longer than 2000 lines, read in chunks using `offset` and `limit`.
1. Split the report body by lines matching the regex `^## .+` (standard Markdown H2). Content above the first H2 heading is the preamble — assign it the synthetic heading `"(preamble)"`.
1. For each section, capture:
   - `heading` — the H2 title verbatim, leading `## ` stripped, trimmed.
   - `body` — every line between this H2 and the next H2 (or end-of-file).
   - `word_count` — count of whitespace-separated tokens in the body.

## Step 2: Classify each section

For each section, check the `heading` against the effective `NOISE_SECTIONS` list (defaulting to the constant; if Phase 1.5 feedback added or removed entries, use the updated list recorded under `state.md` `EffectiveNoiseSections:`).

- Classification is a case-insensitive substring match: a section whose heading contains any of the noise entries (case-insensitive) is classified `noise`. All other sections — including the synthetic `(preamble)` — are classified `content`.
- Record each section's classification. `noise` sections are excluded from atomization windows. `content` sections feed Step 3.

## Step 3: Partition retained content into atomization windows

Take the sections classified `content` in document order and partition them into sequential windows of at most `ATOMIZATION_WAVE_WORD_CAP` (450) words.

Packing rules — apply in this order:

1. **Prefer H2 boundaries.** Start a new window whenever adding the next full section would push the running total above 450 words. Never merge two sections into a window if their combined word count exceeds 450.
1. **Split oversize sections at sentence boundaries.** If a single section exceeds 450 words on its own, split its body at sentence terminators (`.`, `!`, `?` followed by whitespace). Accumulate sentences into the current window until adding the next one would exceed 450 words, then close the window and start the next. The section's heading is recorded on every window it spans.
1. **Never split mid-sentence.** A window must always end at a sentence terminator or at an H2 boundary — never mid-word or mid-clause.

For each window, record:

- `window_index` (zero-based).
- `start_section` — the first H2 heading the window begins in.
- `end_section` — the last H2 heading the window ends in (often equal to `start_section`).
- `word_count` — final word count of the window (≤ 450 unless a single unsplittable sentence exceeds 450 — log that as `oversize_sentence: true` and warn in `state.md`).
- `body` — the verbatim window text (preserve the content; Step 4 writes only boundary metadata, but the full windows feed Phase 2).

Store the per-window bodies in memory (or write them to `.mz/task/<task_name>/windows/window_<N>.md` if the orchestrator prefers to cache them on disk) so Phase 2 can extract them without re-parsing the source report.

## Step 4: Write `parsed_report.md`

Write `.mz/task/<task_name>/parsed_report.md` using exactly this YAML shape:

```yaml
report_path: <absolute path to the report>
total_words: N
sections:
  - heading: "(preamble)"
    classification: content
    word_count: N
  - heading: "Background"
    classification: content
    word_count: N
  - heading: "Methodology"
    classification: noise
    word_count: N
  # one entry per detected H2 section, in document order
noise_excluded:
  - "Methodology"
  - "Vote Tally"
content_retained:
  - "(preamble)"
  - "Background"
  - "Findings"
atomization_windows: N
window_boundaries:
  - window_index: 0
    start_section: "(preamble)"
    end_section: "Background"
    word_count: 412
  - window_index: 1
    start_section: "Findings"
    end_section: "Findings"
    word_count: 449
```

The `noise_excluded` and `content_retained` lists are deduped strings in document order — the user reads these first in Phase 1.5 before inspecting the detailed `sections:` list.

## Step 5: Update state and return

Update `.mz/task/<task_name>/state.md`:

- `Phase: 1_complete`
- `Status: parse_ready`
- `ParsedReportPath: .mz/task/<task_name>/parsed_report.md`
- `AtomizationWindows: <N>`
- `NoiseExcludedCount: <N>`
- `ContentRetainedCount: <N>`

If Phase 1.5 fed back an edited noise list and this is a re-run, also record:

- `EffectiveNoiseSections: [<list of active noise headings>]`
- `NoiseListRevision: <N>` (increment each re-run)

Return control to `SKILL.md` Phase 1.5. The gate is responsible for the Read + verbatim presentation of `parsed_report.md` — do not present the parse from inside this phase file.

## Error handling

- **Report has zero H2 headings** → the entire body is the synthetic `(preamble)` section. This is valid. Record `HeadingStructure: flat` in `state.md` and proceed to windowing against the single content section.
- **A single section exceeds 450 words and has no sentence terminators** (e.g., a monolithic code block or a table) → emit `STATUS: BLOCKED` in the orchestrator, record `BlockedSection: "<heading>"` and `BlockerReason: no_sentence_boundaries` in `state.md`, escalate via AskUserQuestion asking whether to force-split on paragraph breaks or skip the section.
- **All sections classified as noise** → halt with `Status: blocked_all_noise` and escalate via AskUserQuestion — this is almost always a bad noise list and the user should adjust it.
- **Report file unreadable or missing after Phase 0 resolved it** → halt with `Status: blocked_report_vanished` and escalate.

## Common Rationalizations

| Rationalization                                                            | Rebuttal                                                                                                                                                                                 |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Just use regex on the full body — skip the section-level classification." | "H2 classification is what lets the user trust the noise filter. A flat regex-on-body approach produces windows that silently include methodology paragraphs the user asked to exclude." |
| "If a section exceeds 450 words, trim it to 450 and keep going."           | "Trimming drops the tail of the section without the user's approval — they will never know what was cut. Split on sentences so every word reaches Phase 2."                              |
| "Skip the `(preamble)` synthetic heading — it is not an H2."               | "The preamble often contains the report's framing claims. Dropping it silently loses the single most atomizable section of many reports."                                                |
