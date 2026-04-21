---
name: vault-schema
description: ALWAYS invoke when validating vault frontmatter schema, migrating vault notes to a new schema, or checking note-type frontmatter compliance. Triggers: vault schema, frontmatter validation, schema migration.
argument-hint: '<validate|migrate> [vault path]'
model: sonnet
allowed-tools: Agent, Read, Write, Grep, Glob, Bash, AskUserQuestion
---

# Vault Schema

## Overview

Discipline skill that manages a flat YAML schema DSL at `.mz/vault-schema.yml` and governs vault frontmatter compliance. The `validate` mode dispatches `schema-validator` to produce severity-labeled findings against declared note_types. The `migrate` mode turns `Critical:` findings into an approval-gated migration plan, writes a rollback manifest before any write, and patches non-conforming frontmatter only after explicit user approval.

## When to Use

Invoke when declaring a vault schema, checking notes against an existing schema, or back-filling missing frontmatter after a schema change. Trigger phrases: "validate my vault schema", "run schema migration", "check frontmatter compliance".

### When NOT to use

- Editing note body content — use `Edit` directly.
- Orphan detection, broken-link sweeps, or stub audits — use `vault-health`.
- Renaming or moving notes across the vault — use `vault-refactor`.
- Adding links to existing notes — use `vault-connect`.

## Arguments

`$ARGUMENTS` is `<mode> [vault path]` where `<mode>` is `validate` (default) or `migrate`. If the mode is omitted, default to `validate`. If the vault path is omitted, resolve from `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env, then walk up from the working directory looking for `.obsidian/`. If no path resolves, escalate via AskUserQuestion — never guess.

## Constants

- **SCHEMA_PATH**: `.mz/vault-schema.yml` — relative to vault root.
- **TASK_DIR**: `.mz/task/`
- **MAX_MIGRATION_BATCH**: 50 — hard cap on notes patched per migrate run.
- **REPORT_PREVIEW_WORDS**: 200 — truncation cap if an approval gate needs a preview.

## Core Process

### Phase Overview

| Phase | Goal                      | Details              |
| ----- | ------------------------- | -------------------- |
| 0     | Setup                     | Inline below         |
| 1     | Validate                  | `phases/validate.md` |
| 1.5   | User approval — findings  | Inline below         |
| 2     | Plan migration + rollback | `phases/migrate.md`  |
| 2.5   | User approval — plan      | Inline below         |
| 3     | Apply frontmatter patches | `phases/migrate.md`  |

Phases 2, 2.5, and 3 run only when `<mode>` is `migrate`. In `validate` mode the skill stops after Phase 1.5 approval and reports the findings as-is.

### Phase 0: Setup

1. Parse `$ARGUMENTS` for `<mode>` (default `validate`) and `[vault path]`.
1. Resolve vault path via the ladder in the Arguments section. Escalate via AskUserQuestion if nothing resolves.
1. Compute `SCHEMA_PATH` as `<vault>/.mz/vault-schema.yml`.
1. If `SCHEMA_PATH` does not exist, present the bootstrap template from `references/schema-dsl-syntax.md` via AskUserQuestion: "No schema found at `<path>`. A v1 template is below — reply `accept` to write it to `SCHEMA_PATH` and continue, `edit` to provide your own schema text, or `abort` to stop." On `accept`, write the template. On `edit`, accept the user's pasted YAML. On `abort`, halt cleanly. Never fabricate a schema.
1. Derive `task_name = <YYYY_MM_DD>_vault-schema_<mode>` where `<YYYY_MM_DD>` is today's date (underscores); on same-day collision append `_v2`, `_v3`. Create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Mode: <validate|migrate>`, `Vault: <path>`, `SchemaPath: <path>`.
1. Print a visible setup block showing `task_name`, resolved vault path, mode, and schema path.

### Phase 1 — Validate

See `phases/validate.md`.

### Phase 1.5: User approval — findings

**This orchestrator** (not a subagent) must present findings to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before invoking AskUserQuestion, Read `.mz/task/<task_name>/validation_report.md` and capture its full contents.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Validation findings ready for review**
Schema validation complete. Review the findings below and decide whether to proceed with migration or abort.

- **Approve** → findings approved, proceed to Phase 2 (migration planning) if mode is migrate, otherwise mark complete
- **Reject** → abort, no further action
- **Feedback** → incorporate changes, re-run validation, loop back here
```

The question body must contain the verbatim contents of `.mz/task/<task_name>/validation_report.md`. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Invoke AskUserQuestion with the verbatim report body followed by a prompt ending literally with `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

**Response handling**:

- **"approve"** → update state to `findings_approved`. If `Mode: validate`, mark `Status: complete` and stop — nothing is written to the vault in validate mode. If `Mode: migrate`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → incorporate (e.g., "re-scan with a corrected schema", "treat note_type X as pass-through"), re-run Phase 1 if needed, return to this gate and re-present **via AskUserQuestion** (same format, full re-presentation — never diff-only, never summary-only). This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2 — Plan migration + rollback

See `phases/migrate.md` (Step 1 + Step 2).

### Phase 2.5: User approval — migration plan

**This orchestrator** (not a subagent) must present the migration plan to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before invoking AskUserQuestion, Read `.mz/task/<task_name>/migration_plan.md` and capture its full contents.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Migration plan ready for review**
The schema migration plan has been generated. Review the proposed changes and confirm all required placeholders are filled before proceeding.

- **Approve** → plan approved, proceed to Phase 3 (apply patches)
- **Reject** → abort, no vault writes occurred, rollback manifest preserved for reference
- **Feedback** → revise plan and re-present here
```

The question body must contain the verbatim contents of `.mz/task/<task_name>/migration_plan.md`. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Invoke AskUserQuestion with the verbatim plan body followed by a prompt ending literally with `Type **Approve** to proceed, **Reject** to cancel, or type your feedback.`

**Response handling**:

- **"approve"** → update state to `plan_approved`, proceed to Phase 3. The user must have filled in every `"<NEEDS_VALUE>"` and `"<PICK: ...>"` placeholder — Phase 3 re-checks this and loops back here if any remain.
- **"reject"** → update state to `aborted_by_user` and stop. The rollback manifest stays on disk for reference; no vault writes occurred.
- **Feedback** → incorporate edits to the plan (value picks, skip specific notes, adjust proposed frontmatter), re-run Phase 2 to refresh both `migration_plan.md` and `rollback.md`, return to this gate and re-present **via AskUserQuestion** (same format, full re-presentation — never diff-only, never summary-only). This is a loop — repeat until the user explicitly approves. Never apply frontmatter patches without explicit approval.

### Phase 3 — Apply frontmatter patches

See `phases/migrate.md` (Step 4).

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                                            | Rebuttal                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The schema is missing — just validate against sensible defaults."                         | "Pass-through is the declared behavior when a schema is absent. Fabricated defaults invent a contract the user never approved and produce false-positive findings that erode trust across runs. Bootstrap via AskUserQuestion, never guess." |
| "Skip the rollback manifest — patches are trivial, we can undo by hand."                   | "Rollback is non-negotiable. Ctrl-C mid-batch leaves the vault half-patched with no recovery record. The manifest is a disk-persisted artifact that survives context compaction; memory of what changed does not."                           |
| "Auto-pick values for `allowed_values` violations — the user will accept the obvious one." | "Enum picks are irreversible without rollback and 'obvious' is a guess. The skill surfaces `<PICK: ...>` placeholders precisely so the user owns the value, not the orchestrator. Silent auto-pick is how 'helpful' becomes data loss."      |
| "The batch exceeds MAX_MIGRATION_BATCH — just raise the cap inline."                       | "The cap exists so approval-gate review stays human-sized. Raising it inline silently moves the review from 'readable' to 'rubber-stamped'. Split the batch and run again — the gate is load-bearing, not decoration."                       |

## Red Flags

Red Flags: delegated to phase files — see Phase Overview table above.

## Verification

Verification: delegated to phase files — see Phase Overview table above.

## References

Reference: grep `references/schema-dsl-syntax.md` for DSL template, semantics, and v2 candidates.
