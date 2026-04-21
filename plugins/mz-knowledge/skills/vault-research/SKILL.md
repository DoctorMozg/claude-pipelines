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
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `ReportPath: <absolute path>`, `ReportWordCount: <N>`, `Vault: <absolute vault path>`, `PermanentFolder: <extracted folder>`.

### Phase 1.5: User Approval — Noise Exclusion

**This orchestrator** (not a subagent) must present the noise filter results via AskUserQuestion. This step is interactive and must not be delegated. Before presenting, Read `.mz/task/<task_name>/parsed_report.md` in full.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Noise filter results ready for review**
Excluded sections: [list from parsed_report.md]. Retained sections: [list from parsed_report.md].

- **Approve** → proceed to Phase 2 atomization
- **Reject** → abort the task
- **Feedback** → re-run with adjusted exclusions and loop back here
```

Then invoke AskUserQuestion with the full verbatim contents of `parsed_report.md` in the question body. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text. End the question with exactly: `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

Response handling:

- **"approve"** → update `state.md` Status to `noise_filter_approved`, proceed to Phase 2.
- **"reject"** → update `state.md` Status to `aborted_by_user` and stop.
- **Feedback** → typical feedback adds or removes sections from the noise list. Apply the edits to the effective noise list, re-run Phase 1 (`phases/parse_report.md`), and re-present the refreshed `parsed_report.md` **via AskUserQuestion**. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2.5: User Approval — Atomization Proposals

**This orchestrator** (not a subagent) must present the atomization proposals via AskUserQuestion. This step is interactive and must not be delegated. Before presenting, Read `.mz/task/<task_name>/proposals.md` in full.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Atomization proposals ready for review**
Generated N atomic notes from the report. Review the proposed titles, content, and metadata.

- **Approve** → write notes to vault and proceed to Phase 3 link suggestions
- **Reject** → abort the task, no vault writes have occurred
- **Feedback** → adjust proposals (skip, merge, split, retitle) and loop back here
```

Then invoke AskUserQuestion with the full verbatim contents of `proposals.md` in the question body. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text. End the question with exactly: `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

Response handling:

- **"approve"** → update `state.md` Status to `proposals_approved`, continue Phase 2 (post-approval write).
- **"reject"** → update `state.md` Status to `aborted_by_user` and stop. No vault writes have occurred yet.
- **Feedback** → apply feedback (skip numbered proposals, merge, split, retitle), re-run the affected window(s), regenerate `proposals.md`, and re-present **via AskUserQuestion**. Repeat until explicit approval.

### Phase 3.5: User Approval — Link Suggestions

**This orchestrator** (not a subagent) must present the link suggestions via AskUserQuestion. This step is interactive and must not be delegated. Before presenting, Read `.mz/task/<task_name>/link_suggestions.md` in full.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Link suggestions ready for review**
Generated N proposed `[[wikilink]]` insertions connecting notes to existing vault items. Review targets, relationships, and reasons.

- **Approve** → apply all links and complete the task
- **Reject** → skip all links, mark task complete with no Related sections added
- **Feedback** → skip specified links, accept the rest, and loop back here
```

Then invoke AskUserQuestion with the full verbatim contents of `link_suggestions.md` in the question body. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text. End the question with exactly: `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

Response handling:

- **"approve"** → update `state.md` Status to `links_approved`, apply all links, proceed to completion.
- **"reject"** → update `state.md` Status to `complete` with `LinksAdded: 0`, `LinksSkipped: true`. Written notes stay on disk without a Related section.
- **Feedback** → skip specified links, accept the rest, re-present **via AskUserQuestion**. Repeat until explicit approval.

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
  [ ] parsed_report.md shown verbatim via AskUserQuestion before any atomization
  [ ] proposals.md shown verbatim via AskUserQuestion before any vault write
  [ ] link_suggestions.md shown verbatim via AskUserQuestion before any link was written
  [ ] All written notes carry type: research, source_type: research-report, report_path, status: draft
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.
