# Phase 1: Validate Vault Frontmatter Against Schema

## Goal

Dispatch the `schema-validator` agent with the loaded schema and vault path, then collect severity-labeled findings into `.mz/task/<task_name>/validation_report.md` for the Phase 1.5 approval gate.

## Preconditions

Phase 0 has already resolved:

- `vault_path` — the Obsidian vault root.
- `schema_path` — absolute path to `.mz/vault-schema.yml` (the `SCHEMA_PATH` constant).
- `task_name` — the orchestrator task identifier.

If `schema_path` does not exist at this point, Phase 0 must have presented the bootstrap template from `references/schema-dsl-syntax.md` via AskUserQuestion and either written the template or aborted. Do not enter Phase 1 without a readable schema file.

## Actions

### 1. Re-read the schema file

Use the Read tool on `schema_path`. Confirm the file parses as YAML and contains a `note_types:` map. If the file is missing, corrupt, or empty at this point, halt with an explicit error to the user — do not dispatch the validator against an unreadable schema.

### 2. Dispatch `schema-validator` agent

Dispatch the `schema-validator` agent with this task-specific prompt:

```
Vault path: <vault_path>
Schema path: <schema_path>
Output path: .mz/task/<task_name>/validation_report.md
Task name: <task_name>

Read the schema file, glob every .md file under the vault path (excluding .obsidian/), extract frontmatter between --- delimiters, and validate each note against its declared type's rules.

Record findings per note with severity Critical (required-field missing, allowed_values violation) or Nit (unknown-key suggestion). Notes whose type is absent or not declared in note_types are skipped — no finding.

Write the full YAML report to the output path. Return a one-line summary and STATUS + VERDICT.
```

Do not repeat the agent's general process, schema semantics, or output schema — those already live in the agent body.

### 3. Validate the report shape

After the agent completes, Read `.mz/task/<task_name>/validation_report.md` using the Read tool. Confirm:

- The file exists and is non-empty.
- Top-level keys include at least `vault_path`, `schema_path`, `total_notes`, `findings`, `summary`.
- `findings` is a list (may be empty).
- `summary.critical` and `summary.nit` are non-negative integers.

If any check fails, halt and escalate via AskUserQuestion — never fabricate a report or silently retry without user visibility.

### 4. Update state

Patch `.mz/task/<task_name>/state.md`:

- `Status: validation_complete`
- `Phase: 1`
- `ValidationReportPath: .mz/task/<task_name>/validation_report.md`
- `CriticalCount: <summary.critical>`
- `NitCount: <summary.nit>`

### 5. Return to SKILL Phase 1.5 approval gate

Hand control back to `SKILL.md` Phase 1.5. The gate is responsible for the Read + verbatim presentation of `validation_report.md` — do not present findings from inside this phase file.

## Error handling

- **Schema file missing or corrupt** — halt with a pointer to the bootstrap template in `references/schema-dsl-syntax.md` and escalate via AskUserQuestion. Never fabricate a schema.
- **Validator returns `STATUS: NEEDS_CONTEXT`** — re-dispatch once with the missing field explicitly named in the prompt. If the second attempt still returns `NEEDS_CONTEXT`, escalate via AskUserQuestion.
- **Validator returns `STATUS: BLOCKED`** — read the reason, update `state.md` with `Status: blocked`, and escalate via AskUserQuestion. Never auto-retry a blocked dispatch.
- **Validator returns `STATUS: DONE_WITH_CONCERNS` with `schema_missing: true` or `schema_empty: true`** — surface the absence to the user via AskUserQuestion: "The schema at `<schema_path>` was \<missing|empty>. Every note was treated as pass-through. Provide the schema and re-run validate, or confirm pass-through is acceptable." Do not silently proceed to migration.
- **Report shape invalid** — do not proceed to Phase 1.5. The approval gate requires a readable report; a broken report is a failed phase, not an approvable artifact.

## Notes for the approval gate

The Phase 1.5 approval gate inside `SKILL.md` will Read `validation_report.md` and present its full verbatim contents via AskUserQuestion. This phase file's job ends once the report is written and its shape is verified — the presentation belongs to the orchestrator, never to a subagent.
