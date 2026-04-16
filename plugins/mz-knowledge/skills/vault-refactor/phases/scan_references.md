# Phase 1: Scan References

## Goal

Dispatch `vault-refactor-scanner` to enumerate every reference to the old note across the vault, covering every Obsidian Flavored Markdown wikilink form, Bases `link()` formulas, and quoted YAML frontmatter wikilinks. The scanner is read-only on the vault — it writes only to the task directory.

## Step 1: Dispatch `vault-refactor-scanner`

Dispatch the `vault-refactor-scanner` agent (model: sonnet) with this task-specific prompt:

```
Old note:
  basename: "<old basename, no extension>"
  full_path: "<absolute path to old note>"

New name/path:
  value: "<new basename or relative path>"

Vault path: <absolute vault path>
Task dir: .mz/task/<task_name>/
Output path: .mz/task/<task_name>/references_report.md

Your task:

Scan the entire vault (excluding `.obsidian/` and the task directory) for every reference to the old note. Every reference must be captured with path, line number, column, the exact matched text, and the proposed replacement. The replacement must swap ONLY the name token — any alias, heading, or block identifier must be preserved verbatim.

You must cover all twelve reference forms enumerated in your agent system prompt. Do NOT skip form families because you assume they are rare — Bases formulas and quoted frontmatter wikilinks are both silent-failure surfaces if missed.

Write proposals to `.mz/task/<task_name>/references_report.md` using exactly this YAML shape:

old_basename: "<old>"
new_value: "<new>"
vault_path: "<path>"
scanned_at: <ISO timestamp>
total_files: N
total_references: N
forms_detected:
  - <form id from the twelve-form list>
references:
  - path: "<absolute path>"
    form: "<form id>"
    line: N
    column: N
    original: "<exact matched text>"
    replacement: "<proposed replacement>"

Terminal status:
- STATUS: DONE with references_report.md written.
- STATUS: DONE_WITH_CONCERNS if zero references were found — still write the file with empty `references:` list, flag the concern; a rename with zero references is legal but the orchestrator will surface it in the approval gate.
- STATUS: NEEDS_CONTEXT if any required dispatch field is missing.
- STATUS: BLOCKED if the vault path is not readable.
```

## Step 2: Validate report shape

After the agent returns:

1. Read `.mz/task/<task_name>/references_report.md`.
1. Validate the top-level keys: `old_basename`, `new_value`, `vault_path`, `scanned_at`, `total_files`, `total_references`, `forms_detected`, `references`.
1. For each entry under `references:`, validate presence of `path`, `form`, `line`, `column`, `original`, `replacement`.
1. Validate that every `form` value belongs to the twelve-form enumeration: `bare`, `aliased`, `heading`, `block`, `heading-aliased`, `embed-bare`, `embed-file`, `embed-heading`, `embed-block`, `frontmatter-quoted`, `bases-link`, `bases-link-display`.
1. If the file is missing, malformed, or a form value is unrecognized, retry the dispatch once with a clarified prompt that lists the twelve-form enumeration verbatim. Log the retry in `state.md`.
1. Update `state.md`: `Status: references_scanned`, `Phase: 1`, `FilesAffected: <total_files>`, `ReferencesFound: <total_references>`, `FormsDetected: <comma-separated forms_detected>`.

## Step 3: Handoff to approval gate

Return to SKILL Phase 1.5 with the references_report.md ready for verbatim presentation.

The SKILL-level gate requires reading the file into context first, then embedding the full contents inline in the AskUserQuestion body. This phase does NOT invoke AskUserQuestion itself.

## Error handling

- **Scanner `STATUS: DONE_WITH_CONCERNS` (zero references)** → preserve the concern flag in `state.md`; the SKILL gate surfaces it to the user with a warning before allowing approval.
- **Scanner `STATUS: NEEDS_CONTEXT`** → forward the missing-field list to the user via AskUserQuestion; do not fabricate the missing input.
- **Scanner `STATUS: BLOCKED`** → halt the skill immediately; surface the blocker verbatim via AskUserQuestion. Do not retry automatically — a vault-read blocker is a real obstacle, not a transient error.
- **Malformed report after retry** → halt; surface the malformation verbatim via AskUserQuestion; do not attempt a third dispatch.
