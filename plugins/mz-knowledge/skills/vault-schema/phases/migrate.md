# Phase 2 & 3: Plan and Apply Frontmatter Migration

## Goal

Convert the `Critical:` findings in `validation_report.md` into a concrete migration plan, capture a rollback manifest before any write, and apply frontmatter patches to vault notes after the Phase 2.5 approval gate.

This phase file covers two orchestrator phases: Phase 2 (planning, rollback capture, and presentation) and Phase 3 (apply after approval). Phase 2.5 sits between them as an inline approval gate defined in `SKILL.md`.

## Preconditions

Phase 1 has completed with a valid `validation_report.md`. The user has NOT yet approved any vault writes — that approval is gated by Phase 2.5.

Constants in use from `SKILL.md`:

- `MAX_MIGRATION_BATCH: 50` — hard cap on notes patched per run.
- `TASK_DIR: .mz/task/` — root of the task workspace.

## Step 1: Build the migration plan

### 1.1 Read the validation report

Use the Read tool on `.mz/task/<task_name>/validation_report.md`. Parse the YAML. Filter the `findings:` list to entries where `severity: Critical` — `Nit` findings are advisory and never migrated in v1 (see `references/schema-dsl-syntax.md`).

### 1.2 Group findings by note path

Group the filtered Critical findings by `path`. Each note may have multiple Critical findings (e.g., two required fields missing plus an allowed_values violation). Merge them into a single per-note proposed patch.

### 1.3 Propose the frontmatter patch per note

For each grouped note, read the current frontmatter block (between the first two `---` delimiters in the file). Build the proposed patch:

- For `rule_violated: required_field_missing` — add the missing key. Propose a placeholder value the user must review:
  - `status: draft`
  - `created: <today's ISO date>`
  - `tags: []`
  - any other required key the schema declares — use the literal string `"<NEEDS_VALUE>"` so the user sees it must be filled in before the write loops back.
- For `rule_violated: allowed_values_violation` — replace the offending value with a placeholder from the declared enum. Use the literal string `"<PICK: v1 | v2 | v3>"` where `v1`, `v2`, `v3` are the allowed values. The user picks during the approval gate.

Do not auto-pick values. The user reviews every patch before any write.

### 1.4 Enforce the batch cap

Count the notes in the plan. If the count exceeds `MAX_MIGRATION_BATCH` (50), truncate to the first 50 and record the remainder in the plan under `deferred:`. Warn the user via AskUserQuestion before continuing:

"The validation report contains N notes needing migration, which exceeds the MAX_MIGRATION_BATCH cap of 50. The plan covers the first 50; the remaining <N-50> will be deferred. Re-run `/vault-schema migrate` after this batch to process them. Proceed?"

On reject, abort the phase cleanly. On approve, continue to Step 1.5.

### 1.5 Write `migration_plan.md`

Write `.mz/task/<task_name>/migration_plan.md` in YAML format:

```yaml
vault_path: <path>
schema_path: <path>
planned_at: <ISO timestamp>
total_in_plan: N
deferred_count: N
migrations:
  - path: path/to/note.md
    note_type: permanent
    current_frontmatter: |
      title: Existing Title
      created: 2026-03-14
      tags: [idea]
    proposed_frontmatter: |
      title: Existing Title
      created: 2026-03-14
      tags: [idea]
      status: draft
    changes:
      added: [status]
      removed: []
      modified: []
  # one entry per planned note
deferred:
  - path: path/to/other.md
    reason: "batch cap"
```

Update `.mz/task/<task_name>/state.md`:

- `Status: plan_ready`
- `Phase: 2`
- `MigrationPlanPath: .mz/task/<task_name>/migration_plan.md`
- `PlannedCount: <total_in_plan>`
- `DeferredCount: <deferred_count>`

## Step 2: Write the rollback manifest BEFORE any write

The rollback manifest is non-negotiable and must be complete on disk BEFORE Step 3 begins. If Step 3 fails mid-batch, the rollback manifest is the only way to restore the vault to its pre-migration state.

### 2.1 Capture original frontmatter per planned note

For every entry in `migrations:`, Read the note file using the Read tool and capture its full original frontmatter block (between the first two `---` delimiters) along with the entire file content hash (first 16 chars of a SHA-256 equivalent — the skill uses a short Bash step below to generate this).

### 2.2 Write `rollback.md`

Write `.mz/task/<task_name>/rollback.md` in YAML format:

```yaml
vault_path: <path>
task_name: <task_name>
captured_at: <ISO timestamp>
notes:
  - path: path/to/note.md
    original_frontmatter: |
      title: Existing Title
      created: 2026-03-14
      tags: [idea]
    content_hash: "a1b2c3d4e5f6..."
  # one entry per planned note
```

Use this Bash pattern to compute each hash before writing the entry:

```bash
sha256sum "<vault>/<path>" | awk '{print $1}' | cut -c1-16
```

Update `.mz/task/<task_name>/state.md`:

- `Status: rollback_ready`
- `Phase: 2`
- `RollbackPath: .mz/task/<task_name>/rollback.md`

### 2.3 Verify the manifest is complete

Read `rollback.md`. Confirm the `notes:` list length equals `total_in_plan` from the migration plan. If the counts disagree, halt with a Critical error — do not advance to Step 3. A partial manifest cannot be used to restore the vault and makes Step 3 unrecoverable.

## Step 3: Return to Phase 2.5 approval gate

Hand control back to `SKILL.md` Phase 2.5. The gate is responsible for the Read + verbatim presentation of `migration_plan.md` — do not present the plan from inside this phase file.

The Phase 2.5 gate ends with one of three responses:

- `approve` → continue to Step 4 (apply).
- `reject` → update `state.md` Status to `aborted_by_user`, halt. The rollback manifest stays on disk for reference; no vault writes occurred.
- Feedback → re-run Step 1 (re-plan) incorporating the user's edits (e.g., "change `status` placeholder to `evergreen` for note X"), re-run Step 2 (refresh the rollback manifest against the edited plan), and re-present the plan through Phase 2.5. This is a loop — never apply without explicit approval.

## Step 4: Apply frontmatter patches

This step runs ONLY after Phase 2.5 returns `approve` AND after the user has filled in every `"<NEEDS_VALUE>"` and `"<PICK: ...>"` placeholder in the plan.

### 4.1 Verify plan is fully resolved

Re-read `migration_plan.md`. Scan every `proposed_frontmatter` entry for the strings `"<NEEDS_VALUE>"` or `"<PICK:`. If any remain, halt and re-present the plan via the Phase 2.5 approval gate — do not write placeholders to vault files.

### 4.2 Apply patches one note at a time

For each entry in `migrations:`:

1. Read the note file using the Read tool. Confirm the current frontmatter block matches `current_frontmatter` in the plan — if it does not, the file has drifted since planning. Halt on drift and emit rollback instructions (see Error handling).
1. Construct the new file content: replace the frontmatter block (everything between the first two `---` delimiters, inclusive of the delimiters) with the `proposed_frontmatter` block wrapped in its own `---` delimiters. Preserve the body unchanged — every character after the closing `---` of the original frontmatter stays identical.
1. Write the file using the Write tool.
1. Re-read the file and confirm the new frontmatter block is present. If verification fails, halt and emit rollback instructions.

### 4.3 Log each write

Append to `.mz/task/<task_name>/migration_log.md`:

```
<ISO timestamp>  PATCHED  <path>  added=<keys> modified=<keys>
```

### 4.4 Finalize state

After the last patch, update `.mz/task/<task_name>/state.md`:

- `Status: complete`
- `Phase: 3`
- `Completed: <ISO timestamp>`
- `MigratedCount: <count>`
- `RollbackPath: .mz/task/<task_name>/rollback.md`

Print to the user:

```
Migration complete: <N> notes patched.
Rollback manifest preserved at .mz/task/<task_name>/rollback.md
To undo, restore each note's frontmatter from the manifest before further edits.
```

## Error handling

- **Plan contains unresolved placeholders (`<NEEDS_VALUE>` or `<PICK:`)** → halt Step 4 and re-present the plan via Phase 2.5. Never write placeholders.
- **File drift detected in Step 4.2** (current frontmatter no longer matches `current_frontmatter` in the plan) → halt immediately, update state Status to `blocked_file_drift`, emit rollback instructions pointing to `rollback.md`, and escalate via AskUserQuestion. Do not overwrite a drifted file — re-run validate to pick up the latest state.
- **Write failure mid-batch** → halt immediately. Print: "Migration halted after <N of M> writes. Restore the partial batch using `.mz/task/<task_name>/rollback.md` — each entry's `original_frontmatter` must be pasted back into the corresponding file before further edits." Update state Status to `halted_mid_batch`. Do not auto-rollback; the user confirms the restore step by step.
- **Rollback manifest count mismatch in Step 2.3** → halt before Step 3, update state Status to `blocked_rollback_incomplete`, escalate via AskUserQuestion. A partial manifest is worse than no manifest.
- **Validator report missing required fields** → should never happen if Phase 1 succeeded; if it does, the report is corrupt. Halt, mark state Status `blocked_report_corrupt`, escalate.

## Why rollback BEFORE write

The rollback manifest is the recovery artifact. Writing it AFTER a patch means a Ctrl-C between steps leaves the vault with a half-migrated note and no restoration record. Writing it BEFORE every write guarantees that any partial run is recoverable from disk state alone, even if the orchestrator's conversation context is lost to compaction.
