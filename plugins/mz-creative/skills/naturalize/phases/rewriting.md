# Phase 1: Rewrite + Phase 2: Check and Apply

## Phase 1: Rewrite (expert-naturalizer)

### 1.1 Paths

```
output_path = <PROJECT_ROOT>/.mz/task/<task_name>/output.md
report_path = <PROJECT_ROOT>/.mz/reports/<task_name>.md
```

`input.md` in the same task folder holds the verbatim input from Phase 0. For `@file:` input it is the kept original, so nothing writes to it after setup.

### 1.2 Optional web research (`research:yes` only)

Skip this step unless the user passed `research:yes`. Otherwise dispatch `pipeline-web-researcher` (mz-base) with this brief:

```
Topic: Current high-frequency AI-generated text patterns (single words, phrases, structural patterns, punctuation tells), 2025 to 2026 data
Sources to prioritize: Wikipedia Signs_of_AI_writing, Pangram Labs blog, GPTZero news, peer-reviewed corpus studies (FSU, OpenAlex, arXiv), practitioner ban lists (jodiecook.com, contentbeta.com)
Banned: AI-generated detection lists, undated blogs, social posts
Output: only patterns missing from the embedded list below, focused on what is new since 2024
Embedded list (do not repeat these): <the avoid lists from expert-naturalizer.md, abbreviated>
Return the findings inline.
```

The researcher is read-only, so write its response verbatim to `<PROJECT_ROOT>/.mz/task/<task_name>/web_research.md` yourself and add that path to `FilesWritten`.

### 1.3 Dispatch expert-naturalizer

Compose a compact dispatch. Don't repeat the agent's general instructions: the agent file is self-contained and runs its own pattern detection.

```
Mode: standalone rewrite
Input file: <PROJECT_ROOT>/.mz/task/<task_name>/input.md
Output file: <output_path>
Report file: <report_path>
Preserve: <terms from preserve:, or "none beyond auto-preserve">
Specificity gaps: list each vague claim in the report; the output replaces the user's text, so it carries no [SPECIFICITY NEEDED] marker
Medium: <from the file's extension or path when obvious, else omit this line>
Long-document handling: <chunk by H2 if the input exceeds CHUNK_THRESHOLD words, else single pass>
Extra patterns: <only after step 1.2: read <PROJECT_ROOT>/.mz/task/<task_name>/web_research.md and add its patterns to this rewrite's pass list; omit this line otherwise>
```

Dispatch it as a single Agent tool call with `subagent_type: expert-naturalizer` and wait for it. Update `state.md` before and after.

### 1.4 Validate the rewrite

1. `output_path` and `report_path` both exist and are non-empty.
1. The agent emitted `STATUS: DONE` or `STATUS: DONE_WITH_CONCERNS`.
1. `output_path` holds only the rewritten text. If the agent appended a `## Naturalization report` section anyway, move that section and the `---` above it into `report_path`.
1. Code blocks, tables and every `preserve:` term from the input still appear in the output.
1. `output_path` holds no `[SPECIFICITY NEEDED]` marker, because Phase 2 copies it over the user's file. Delete any marker that slipped through with Edit, leaving its sentence as written, and add that sentence to `report_path` under the specificity gaps.

On `BLOCKED`, leave the user's file untouched and escalate via AskUserQuestion. On `NEEDS_CONTEXT`, re-dispatch once with the missing context, usually a clearer preserve list.

Update `state.md`: `Phase: 1`, `phase_complete: true`, and add `output_path` and `report_path`, relative to the project root, to `FilesWritten`.

## Phase 2: Check and Apply

### 2.1 Punctuation check

Run `<PUNCTUATION_CHECK> <preserve flags> <output_path>` as a command of its own, not chained with `;` or `&&`, because the skill's Bash grant matches only that command. `<preserve flags>` is one `--preserve '<term>'` per `PreserveTerms` entry, or nothing when there are none, since the rewrite keeps those terms verbatim. It checks prose only; code, URLs, quotes and preserved terms are skipped, and the change report in `report_path` isn't checked at all.

- **Exit 0**: the rewrite is clean. Set `PunctuationCheck: clean`.

- **Exit 1**: each stdout line reads `file:line: <name> <char>`. Re-dispatch `expert-naturalizer` once:

  ```
  Mode: punctuation fix
  Input file: <output_path>
  Output file: <output_path>
  Lines to fix:
  <the check's stdout>
  Restructure each flagged sentence so the banned character is gone: a period, a comma, parentheses or a conjunction, never a spaced hyphen, `--` or `...` in its place. Change nothing else and write no report.
  ```

  Run the check again. Exit 0 sets `PunctuationCheck: clean`. A second exit 1 sets `PunctuationCheck: concerns`; keep its lines for the final block and carry on: the rewrite is still applied, and those lines tell the user exactly what is left to fix by hand.

- **Exit 2**: the check couldn't read the file. Set `PunctuationCheck: not run` with its stderr and carry on.

### 2.2 Apply

- **Inline input** (`InputSource: inline`): show the rewritten text from `output_path` in the chat. Set `FileUpdateApplied: n/a`.
- **File input** (`InputSource: file:<path>`): read `output_path` and write its contents to `<path>` with the Write tool, not `cp`, so the user's file-edit permissions apply. Ask nothing, since the original stays in `input.md`. Then run `diff -u <PROJECT_ROOT>/.mz/task/<task_name>/input.md <path>` on its own; exit 1 only means the files differ. Show the diff in the chat, cut to its first 60 lines with a note giving the full command when it runs longer. Set `FileUpdateApplied: yes`.

If `<path>` can no longer be written, leave it alone, set `FileUpdateApplied: no`, and point the user at `output_path`.

## Final output

Set `Phase: complete`, `Status: complete`, `phase_complete: true` and `what_remains: []` in `state.md`. Then emit the final block defined in SKILL.md under Verification. When `PunctuationCheck` is `concerns` or `not run`, the block's `Punctuation` line says so and lists the lines or the reason.
