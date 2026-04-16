# Phase 1: Detect Tooling and Transcribe

## Goal

Verify the right transcription or OCR tool is available for the detected modality, record the tool chain to `tooling.md`, dispatch `capture-normalizer` to produce a clean transcript under `.mz/task/<task_name>/transcript.md`, then return to SKILL Phase 1.5 for user approval.

## Step 1: Detect tooling (mandatory before dispatch)

For the modality resolved in Phase 0, run `which` checks in the order below. Record every result — present AND missing — to `.mz/task/<task_name>/tooling.md` so downstream skills can read the same detection instead of re-running it.

| Modality | Primary         | Fallback           | Install (primary)          |
| -------- | --------------- | ------------------ | -------------------------- |
| voice    | `whisper-cpp`   | `whisper` (openai) | `brew install whisper-cpp` |
| image    | `ocrit` (macOS) | `tesseract`        | `brew install tesseract`   |
| pdf      | `pdftotext`     | —                  | `brew install poppler`     |
| youtube  | `yt-dlp`        | —                  | `brew install yt-dlp`      |

Run the checks via `Bash`:

```bash
which whisper-cpp || true
which whisper || true
which ocrit || true
which tesseract || true
which pdftotext || true
which yt-dlp || true
```

Write `tooling.md` as YAML:

```yaml
checked_at: <ISO timestamp>
modality: <voice|image|pdf|youtube>
voice:
  primary: whisper-cpp
  primary_path: <path or null>
  fallback: whisper
  fallback_path: <path or null>
image:
  primary: ocrit
  primary_path: <path or null>
  fallback: tesseract
  fallback_path: <path or null>
pdf:
  primary: pdftotext
  primary_path: <path or null>
  fallback: null
youtube:
  primary: yt-dlp
  primary_path: <path or null>
  fallback: null
selected_tool: <name of tool selected for dispatch>
selected_tool_path: <resolved absolute path>
```

## Step 2: Select the tool or escalate

Selection order:

1. If the modality's primary tool resolved to a path, select it.

1. Otherwise, if the modality's fallback tool resolved to a path, select the fallback and note the degradation in `state.md` under `ToolFallback: true`.

1. Otherwise (both primary and fallback missing, or primary missing for a modality with no fallback), escalate via `AskUserQuestion`. Name the install command for the primary tool and offer two options:

   ```
   No transcription tool found for modality <modality>.

   Required: <primary tool name>
   Install command: <install command from the table above>

   Options:
     - "install" — you have installed the tool; retry detection.
     - "abort" — cancel this capture.
   ```

   On `install` response, re-run Step 1 once. If the tool still does not resolve, emit `STATUS: BLOCKED` to the caller with the missing tool and install command. Do not proceed to dispatch.

Update `state.md`: `Phase: 1`, `Status: tooling_selected`, `SelectedTool: <name>`, `ToolingPath: .mz/task/<task_name>/tooling.md`.

## Step 3: Modality-specific sanity checks

Run these checks inline before dispatch — they protect the user from accidentally transcribing a 4-hour meeting or a 500-page PDF:

- **voice**: if the audio file duration exceeds `VOICE_MAX_DURATION_SEC` (3600), ask via AskUserQuestion whether to proceed. Use `ffprobe -v error -show_entries format=duration -of csv=p=0 <path>` when `ffprobe` is available; otherwise skip the check and note it in state.
- **pdf**: if the PDF page count exceeds `PDF_MAX_PAGES` (50), ask via AskUserQuestion whether to proceed. Use `pdfinfo <path> | awk '/^Pages/ {print $2}'` when `pdfinfo` is available; otherwise skip and note.
- **image**: no size check — OCR cost scales with image, not content volume.
- **youtube**: no pre-check; `yt-dlp` handles availability internally.

## Step 4: Dispatch capture-normalizer

Dispatch the `capture-normalizer` agent (model: haiku) with the prompt below. Fill the placeholders from Phase 0 and Step 2.

```
Input:
  source: <absolute path or URL>
  modality: <voice|image|pdf|youtube>
  primary_tool: <tool name from tooling.md.selected_tool>
  primary_tool_path: <resolved absolute path>
  fallback_tool: <fallback name if primary failed in a previous attempt, else null>

Output:
  transcript_path: .mz/task/<task_name>/transcript.md

Your task:

1. Invoke the selected tool for the modality using the Bash tool. Use the exact command recipes below:

   - voice + whisper-cpp:
       whisper-cpp -m <model path> -f <source> -otxt -of .mz/task/<task_name>/whisper_raw
       (model path defaults to the environment's configured ggml model; if unknown, fall back to `whisper`)

   - voice + whisper (openai):
       whisper <source> --model base --output_format txt --output_dir .mz/task/<task_name>/

   - image + ocrit:
       ocrit <source>

   - image + tesseract:
       tesseract <source> - -l eng

   - pdf + pdftotext:
       pdftotext -layout <source> -

   - youtube + yt-dlp:
       yt-dlp --write-auto-sub --sub-lang en --skip-download -o ".mz/task/<task_name>/yt_%(title)s" <source>
       then:
       grep -v "^[0-9]" .mz/task/<task_name>/yt_*.en.vtt | grep -v "^$" | awk '!seen[$0]++'

2. Clean the output:
   - Trim leading/trailing whitespace.
   - Collapse runs of more than 2 consecutive blank lines into a single blank line.
   - For VTT output, strip timestamp lines (already covered by the awk pipeline above).
   - For PDF output, remove repeated page-number footer lines and bare page-break artifacts.
   - Preserve paragraph breaks.
   - Never invent content to patch inaudible/illegible gaps — leave `[inaudible]` or `[unclear]` markers where the tool emitted them.

3. Write the cleaned transcript to transcript_path as:

   ---
   modality: <voice|image|pdf|youtube>
   tool_used: <name of tool actually invoked>
   duration_or_pages: <seconds, pages, or "n/a">
   captured_at: <ISO timestamp>
   ---

   <transcript body>

Terminal status:
- STATUS: DONE — transcript written and non-empty.
- STATUS: DONE_WITH_CONCERNS — transcript written but looks truncated, very short, or mostly unclear-markers; name the concern in one sentence.
- STATUS: NEEDS_CONTEXT — dispatch field missing (source/modality/output_path).
- STATUS: BLOCKED — tool invocation failed; name the exact error and the command that failed.
```

## Step 5: Validate transcript artifact

After the agent returns:

1. Read `.mz/task/<task_name>/transcript.md`.
1. Check:
   - File exists and parses as frontmatter + body.
   - Frontmatter contains `modality`, `tool_used`, `duration_or_pages`, `captured_at`.
   - Body is non-empty (at least 1 non-whitespace character after the frontmatter closing `---`).
1. If the body is empty, do not proceed. Ask via AskUserQuestion whether to retry with the fallback tool (if available and not yet tried) or abort.
1. If the agent returned `STATUS: DONE_WITH_CONCERNS`, record the concern in `state.md` under `CaptureConcern: "<one-line concern>"`. Continue to Phase 1.5 — the user decides on approval.
1. Update `state.md`: `Phase: 1`, `Status: transcript_ready`, `TranscriptPath: .mz/task/<task_name>/transcript.md`, `TranscriptWordCount: <N>`.

## Step 6: Return to SKILL Phase 1.5

Hand control back to SKILL.md Phase 1.5. The orchestrator (not a subagent) then Reads `transcript.md`, formats the verbatim presentation, and invokes AskUserQuestion per the approval-gate structure in SKILL.md.

## Constraints

- Never write to the vault in this phase. Phase 1 produces only `transcript.md` and `tooling.md` under `TASK_DIR/<task_name>/`.
- Never silently proceed when a tool is missing. Escalate via AskUserQuestion with the install command.
- Never skip Step 1 detection. Stale conversation memory of "last run's whisper path" is not safe — the path may have moved between runs.
- On feedback from Phase 1.5 asking to "try the other tool", flip `primary` and `fallback` for the modality in `tooling.md`, mark `ToolFallback: true` in state, re-run Step 4 with the alternative tool. Do not loop more than twice without escalating.
