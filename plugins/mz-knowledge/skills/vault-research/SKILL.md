---
name: vault-research
description: 'ALWAYS invoke when injecting a research report or brainstorm report from .mz/research or .mz/reports into the vault as atomized notes. Triggers: ingest research, import report, atomize report, research to notes.'
argument-hint: <report path>
model: opus
allowed-tools: Agent, Read, Write, Grep, AskUserQuestion
---

# Vault Research

## Overview

Discipline skill that atomizes a long research report into permanent notes, pre-filtering known noise sections before atomization. Reuses `atomization-proposer` (dispatched once per 450-word window — matches the agent's 500-word input cap) and `link-suggester`. Produces claim-style atomic notes under the vault's permanent folder inside a `research/` subfolder, each carrying `type: research`, `source_type: research-report`, and full provenance.

## When to Use

- Importing research outputs, brainstorm reports, or deep-research reports from `.mz/research/` or `.mz/reports/`.
- Converting long structured reports (panel deliberations, methodology sections, cut ideas) into separately linkable permanent notes while discarding pre-known noise sections.

### When NOT to use

- Capturing raw multimodal input (voice memos, images, PDFs, YouTube) — use `vault-ingest`.
- Processing existing fleeting notes already in the vault — use `process-notes`.
- Proposing `[[wikilinks]]` between notes that already exist — use `vault-connect`.

## Constants

- **TASK_DIR**: `.mz/task/`
- **MAX_NOTES**: 15 (hard cap across all atomization windows; excess proposals are deduped and truncated)
- **LONG_REPORT_THRESHOLD_WORDS**: 2000 (warn the user before proceeding on reports above this size)
- **ATOMIZATION_WAVE_WORD_CAP**: 450 (per-window word budget; `atomization-proposer` caps at 500 so 450 leaves headroom)
- **NOISE_SECTIONS**: `["Vote Tally", "Voting History", "Panel Perspectives", "Methodology", "Deliberately Cut", "All Ideas by Round"]`

## Core Process

| #   | Phase                      | Reference                              | Loop?          |
| --- | -------------------------- | -------------------------------------- | -------------- |
| 0   | Setup                      | inline                                 | —              |
| 1   | Parse + noise filter       | `phases/parse_report.md`               | —              |
| 1.5 | Approval — noise exclusion | inline                                 | until approved |
| 2   | Atomize + write            | `phases/atomize_and_write.md`          | —              |
| 2.5 | Approval — proposals       | inline                                 | until approved |
| 3   | Link suggestions           | `phases/atomize_and_write.md` (Step 5) | —              |
| 3.5 | Approval — links           | inline                                 | until approved |

### Phase 0: Setup

1. Resolve `$ARGUMENTS` as an absolute report path. The path must exist — if it does not, ask the user via AskUserQuestion for a corrected path.
1. If the resolved path is not under `.mz/research/` or `.mz/reports/`, warn the user but do not block — record `NonStandardLocation: true` in `state.md`.
1. Read the report and compute word count. If it exceeds `LONG_REPORT_THRESHOLD_WORDS` (2000), record `LongReport: true` and warn the user before proceeding.
1. Resolve the vault path and read vault CLAUDE.md. Extract the permanent folder convention (e.g., `04 - Permanent/`, `permanent/`, `notes/permanent/`). If no permanent folder convention is found, ask via AskUserQuestion — never guess.
1. Derive `task_name = <YYYY_MM_DD>_vault-research_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<slug>` is a filename-sanitized form of the report basename; on same-day collision append `_v2`, `_v3`. Create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `schema_version: 2`, `phase_complete: false`, `what_remains: []`, `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `ReportPath: <absolute path>`, `ReportWordCount: <N>`, `Vault: <absolute vault path>`, `PermanentFolder: <extracted folder>`.

### Phase 1.5: User Approval — Noise Exclusion

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/parsed_report.md` in full and capture its contents into context.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a normal markdown chat message:

```
## Noise filter results ready for review — vault-research

<verbatim contents of .mz/task/<task_name>/parsed_report.md>

---
**Approve** → proceed to Phase 2 atomization  ·  **Reject** → abort the task  ·  reply with feedback to revise
```

Emit the full verbatim contents of `.mz/task/<task_name>/parsed_report.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the artifact in the question body:

- question: `The noise filter results above are ready for review.`
- options: **Approve** — proceed to Phase 2 atomization · **Reject** — abort the task

**Response handling**:

- **Approve** → update `state.md` Status to `noise_filter_approved`, proceed to Phase 2.
- **Reject** → update `state.md` Status to `aborted_by_user` and stop.
- **Any other reply (feedback)** → typical feedback adds or removes sections from the noise list. Apply the edits to the effective noise list, re-run Phase 1 (`phases/parse_report.md`), overwrite `parsed_report.md`, return to Surface 1, re-read the updated artifact, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2.5: User Approval — Atomization Proposals

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/proposals.md` in full and capture its contents into context.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a normal markdown chat message:

```
## Atomization proposals ready for review — vault-research

<verbatim contents of .mz/task/<task_name>/proposals.md>

---
**Approve** → write notes to vault and proceed to Phase 3 link suggestions  ·  **Reject** → abort the task, no vault writes have occurred  ·  reply with feedback to revise
```

Emit the full verbatim contents of `.mz/task/<task_name>/proposals.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the artifact in the question body:

- question: `The atomization proposals above are ready for review.`
- options: **Approve** — write notes to vault and proceed to Phase 3 link suggestions · **Reject** — abort the task, no vault writes have occurred

**Response handling**:

- **Approve** → update `state.md` Status to `proposals_approved`, continue Phase 2 (post-approval write).
- **Reject** → update `state.md` Status to `aborted_by_user` and stop. No vault writes have occurred yet.
- **Any other reply (feedback)** → apply feedback (skip numbered proposals, merge, split, retitle), re-run the affected window(s), regenerate `proposals.md`, return to Surface 1, re-read the updated artifact, and re-emit the entire plan message from scratch. This is a loop — repeat until explicit approval.

### Phase 3.5: User Approval — Link Suggestions

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `.mz/task/<task_name>/link_suggestions.md` in full and capture its contents into context.

**Surface 1 — emit the plan message.** Output the artifact verbatim as a normal markdown chat message:

```
## Link suggestions ready for review — vault-research

<verbatim contents of .mz/task/<task_name>/link_suggestions.md>

---
**Approve** → apply all links and complete the task  ·  **Reject** → skip all links, mark task complete with no Related sections added  ·  reply with feedback to revise
```

Emit the full verbatim contents of `.mz/task/<task_name>/link_suggestions.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the artifact in the question body:

- question: `The link suggestions above are ready for review.`
- options: **Approve** — apply all links and complete the task · **Reject** — skip all links, mark task complete with no Related sections added

**Response handling**:

- **Approve** → update `state.md` Status to `links_approved`, apply all links, proceed to completion.
- **Reject** → update `state.md` Status to `complete` with `LinksAdded: 0`, `LinksSkipped: true`. Written notes stay on disk without a Related section.
- **Any other reply (feedback)** → skip specified links, accept the rest, overwrite `link_suggestions.md`, return to Surface 1, re-read the updated artifact, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never proceed without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                  | Rebuttal                                                                                                                                                                                               |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Send the whole report to atomization-proposer in one dispatch." | "atomization-proposer has a 500-word input cap; oversized input returns DONE_WITH_CONCERNS with only partial processing. The 450-word windowing scheme exists to keep every dispatch fully processed." |
| "Noise sections are obvious — skip the user approval gate."      | "The user may want to include methodology or panel-perspectives sections; every exclusion needs explicit approval. Silent drops destroy information the user intended to capture."                     |
| "Run all atomization windows in parallel for speed."             | "Sequential windows are required because each dispatch writes to a numbered output file and shares agent context; parallel writes would collide and produce interleaved output."                       |

## Red Flags

- Dispatching `atomization-proposer` with more than `ATOMIZATION_WAVE_WORD_CAP` words.
- Running atomization windows in parallel instead of sequentially.
- Presenting any approval gate as a path or summary instead of the verbatim artifact contents.
- Writing to the vault root or to `<vault>/<INBOX_FOLDER>/` instead of `<vault>/<permanent_folder>/research/`.
- Omitting `type: research`, `source_type: research-report`, or `report_path` from any note's frontmatter.
- Proceeding past any `.5` approval gate without explicit "approve" from the user.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-research verification:
  [ ] parsed_report.md emitted verbatim as a chat message (Surface 1) and AskUserQuestion selector presented before any atomization
  [ ] proposals.md emitted verbatim as a chat message (Surface 1) and AskUserQuestion selector presented before any vault write
  [ ] link_suggestions.md emitted verbatim as a chat message (Surface 1) and AskUserQuestion selector presented before any link was written
  [ ] All written notes carry type: research, source_type: research-report, report_path, status: draft
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.
