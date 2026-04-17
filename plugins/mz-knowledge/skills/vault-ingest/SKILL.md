---
name: vault-ingest
description: ALWAYS invoke when capturing voice memos, screenshots, PDFs, YouTube videos, or images into the vault as fleeting notes. Triggers ingest audio, transcribe voice, capture screenshot, ingest PDF, capture YouTube.
argument-hint: '<path or URL> [modality hint: voice|image|pdf|youtube]'
model: sonnet
allowed-tools: Agent, Read, Write, Bash, Grep, Glob, AskUserQuestion
---

# Vault Ingest

## Overview

Discipline skill for multimodal capture into the vault as fleeting notes. Detects input modality (voice, image, PDF, YouTube, screenshot), verifies the required transcription or OCR tool is installed, dispatches `capture-normalizer` to produce a clean transcript, presents the transcript for user approval, and writes a frontmatter-annotated fleeting note to the vault inbox. Every capture produces a note with `status: draft`, `type: fleeting`, and full provenance fields so downstream skills (`process-notes`, `vault-schema`) can reason about it.

## When to Use

- Ingesting voice memos (`.m4a`, `.wav`, `.mp3`) into the vault with transcription.
- Capturing screenshots or images (`.png`, `.jpg`, `.heic`) via OCR.
- Importing PDF content into a single fleeting note.
- Capturing YouTube videos via auto-subtitle download.

### When NOT to use

- Processing fleeting notes that are already in the vault — use `process-notes`.
- Atomizing long captured notes into permanent atomic notes — use `process-notes` as a follow-up after capture.
- Proposing `[[wikilinks]]` between notes — use `vault-connect`.
- Importing research reports or brainstorm outputs — use `vault-research`.

## Constants

- **TASK_DIR**: `.mz/task/`
- **INBOX_FOLDER**: `inbox/`
- **MAX_TRANSCRIPT_PREVIEW**: 500 (words shown in the approval gate; longer transcripts are truncated with `...`)
- **VOICE_MAX_DURATION_SEC**: 3600 (warn before transcribing audio longer than 1 hour)
- **PDF_MAX_PAGES**: 50 (warn before extracting from PDFs longer than this)

## Core Process

| Phase | Goal                         | Details                           |
| ----- | ---------------------------- | --------------------------------- |
| 0     | Setup                        | Inline below                      |
| 1     | Detect tooling + transcribe  | `phases/detect_and_transcribe.md` |
| 1.5   | User approval — transcript   | Inline below                      |
| 2     | Write fleeting note to vault | `phases/approve_and_write.md`     |

### Phase 0: Setup

1. Parse `$ARGUMENTS`. First argument is the input path or URL. Second argument (optional) is an explicit modality hint: `voice`, `image`, `pdf`, or `youtube`.
1. If the first argument is empty, ask the user via AskUserQuestion what to ingest. Never guess.
1. Detect modality from the input:
   - Extension `.m4a`, `.wav`, `.mp3` → `voice`.
   - Extension `.png`, `.jpg`, `.jpeg`, `.heic` → `image` (record `source_type: screenshot` if user confirmed it is a screenshot, else `image`).
   - Extension `.pdf` → `pdf`.
   - URL containing `youtube.com` or `youtu.be` → `youtube`.
   - If the second argument is present, it overrides the detected modality.
   - If modality cannot be inferred and no hint was given, ask via AskUserQuestion.
1. Resolve the vault path with precedence: `$OBSIDIAN_VAULT_PATH` → `$MZ_VAULT_PATH` → walk up from cwd to the nearest `.obsidian/` directory. If none found, ask via AskUserQuestion.
1. Derive `task_name = vault-ingest_<modality>_<HHMMSS>` and create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Input: <path or URL>`, `Modality: <voice|image|pdf|youtube>`, `Vault: <absolute path>`.

### Phase 1.5: User Approval — Transcript

**This orchestrator** (not a subagent) must present the transcript to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/transcript.md` and capture the full contents into the orchestrator's context. The question body must contain the verbatim transcript text (truncated at `MAX_TRANSCRIPT_PREVIEW` words with a trailing `...` when longer). Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Transcript Ready for Review**
Transcript produced from <input>. Modality: <modality>, transcription tool: <tool>, duration/pages: <detail>.

- **Approve** → proceed to Phase 2 to write the fleeting note to the vault
- **Reject** → task marked aborted, no fleeting note written
- **Feedback** → re-run Phase 1 with adjusted tool choice, loop back here for re-review
```

Format the question body as:

```
Transcript ready for review (modality: <modality>, tool: <tool>, <duration or pages>).

<verbatim transcript, truncated at MAX_TRANSCRIPT_PREVIEW words with "..." when longer>

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

Response handling:

- **"approve"** → update state to `transcript_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → common feedback is "try a different tool" (switch `whisper-cpp` → `whisper`, `ocrit` → `tesseract`) or "the transcript is truncated, rerun". Incorporate the feedback, re-run Phase 1 with the adjusted tool choice, return to this gate, re-present **via AskUserQuestion** (same format, full re-presentation — never diff-only). This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                               | Rebuttal                                                                                                                                                                                         |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "The tool is missing — just write an empty fleeting note with a source link." | "An empty note with provenance metadata masquerading as captured content is worse than no note at all — it pollutes future search and appears 'processed' when it is not. Escalate via BLOCKED." |
| "Skip the approval gate — the user already chose to capture this."            | "Tool output is noisy: VTT timestamps survive, whisper inserts `[inaudible]`, OCR mangles layout. The approval gate exists so the user sees what the vault will actually contain."               |
| "Transcript has garbage — ship it anyway, the user can fix it in Obsidian."   | "Captured notes are the raw intake layer for the entire pipeline. Bad captures propagate into atomization, linking, and Q&A. Either a fallback tool recovers quality or the user says BLOCKED."  |

## Red Flags

- Dispatching `capture-normalizer` before running `which <tool>` detection.
- Writing a fleeting note with an empty body because the transcription tool failed.
- Presenting the approval gate as a path or one-line status instead of the verbatim transcript.
- Skipping the modality detection step and guessing from filename alone when `$ARGUMENTS[2]` was provided.
- Writing to the vault root or to `<vault>/permanent/` instead of `<vault>/<INBOX_FOLDER>/`.
- Omitting `source_type`, `captured_at`, or `status: draft` from the frontmatter.

## Verification

Print this block before concluding — silent checks get skipped:

```
vault-ingest verification:
  [ ] Tool detection logged to tooling.md before capture-normalizer dispatch
  [ ] Transcript shown verbatim via AskUserQuestion before any vault write
  [ ] Fleeting note written under <vault>/<INBOX_FOLDER>/ with source_type + captured_at + status: draft
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, the skill did not run correctly — report the failure explicitly rather than claiming success.
