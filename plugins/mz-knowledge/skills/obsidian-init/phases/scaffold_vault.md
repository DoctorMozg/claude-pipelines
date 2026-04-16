# Phase 1: Scaffold Vault

## Goal

Create the folder structure, write CLAUDE.md from the template (customized with interview answers), write `.mz/vault-schema.yml`, and create starter note templates. Never overwrite existing files.

## Preconditions

Phase 0.5 returned `approve`. `state.md` records `Vault`, `VaultPurpose`, `PrimaryTopics`, `NoteTypes`, `FrontmatterStyle`, `TagStyle`, `ExistingCLAUDE`, `ExistingSchema`, `ExistingFolders`.

## Step 1: Create folder structure

The default PARA+Zettelkasten layout. Skip folders whose note type the user disabled in the interview.

| Folder            | Note type required | Description                                  |
| ----------------- | ------------------ | -------------------------------------------- |
| `00 - MOCs/`      | moc                | Maps of Content — topic indexes              |
| `01 - Projects/`  | project            | Time-bound work with defined outcomes        |
| `02 - Areas/`     | (always)           | Ongoing responsibilities, no end date        |
| `03 - Resources/` | resource           | Reference material                           |
| `04 - Permanent/` | permanent          | Evergreen atomic notes                       |
| `05 - Fleeting/`  | fleeting           | Raw captures — promote or delete within days |
| `06 - Daily/`     | daily              | Daily notes, YYYY-MM-DD.md                   |
| `07 - Archives/`  | (always)           | Retired notes kept for link integrity        |
| `99 - Meta/`      | (always)           | Templates, attachments, vault-support files  |

For each folder:

1. Check if it already exists (from `ExistingFolders` in state.md or via `ls`).
1. If missing, create with `mkdir -p <vault>/<folder>`.
1. Record in `state.md` under `FoldersCreated: [list]`.

Create topic subfolders under `04 - Permanent/` based on `PrimaryTopics`. For each topic, create `<vault>/04 - Permanent/<Topic>/`. Do not nest deeper — the user adds sub-hierarchy as notes accumulate.

Create `<vault>/99 - Meta/Templates/` for starter templates.
Create `<vault>/.mz/memory/` for project memory.

## Step 2: Write CLAUDE.md

If `ExistingCLAUDE` is true, do NOT overwrite. Instead:

1. Read the existing `<vault>/CLAUDE.md`.
1. Check which sections are missing compared to the template (Vault Context, Obsidian Syntax, Folder Layout, Note Conventions, Compounding Wiki Principle, Don'ts, Rename Safety, Health Checks).
1. If all sections present, skip this step and record `CLAUDEAction: skipped_existing`.
1. If sections are missing, append only the missing sections at the end. Record `CLAUDEAction: appended_missing_sections`.

If `ExistingCLAUDE` is false, write a new CLAUDE.md. Read the template from `references/claude-md-template.md` and customize:

- Replace `{{VAULT_PURPOSE}}` with `VaultPurpose` from state.md.
- Replace `{{VAULT_ROOT}}` with the absolute vault path.
- Replace `{{FOLDER_LAYOUT}}` with the actual folders created in Step 1 (preserving the numbered-prefix format).
- Replace `{{PERMANENT_HIERARCHY}}` with a tree showing each `PrimaryTopics` entry as a top-level subfolder under `04 - Permanent/`, with a placeholder comment `# add subfolders as notes accumulate`.
- Replace `{{FRONTMATTER_TEMPLATE}}` with the frontmatter block matching `FrontmatterStyle`:
  - Minimal: `created`, `type`, `tags`
  - Extended: `created`, `updated`, `type`, `tags`, `status`, `source`, `epistemic_status`
- Replace `{{TAG_STYLE_NOTE}}` with the tag convention matching `TagStyle`:
  - Flat: `Tags are flat: #ai, #engineering, #draft. Avoid nesting.`
  - Hierarchical: `Tags are hierarchical with /: #ai/llm/claude, #status/draft. Prefer a small shared taxonomy over ad-hoc sprawl.`
- Replace `{{NOTE_TYPES_LIST}}` with the pipe-separated list of enabled note types for the `type:` frontmatter field.
- Replace `{{DATE_TODAY}}` with today's date in YYYY-MM-DD format.

Write to `<vault>/CLAUDE.md` using the Write tool. Record `CLAUDEAction: written`.

## Step 3: Write .mz/vault-schema.yml

If `ExistingSchema` is true, skip and record `SchemaAction: skipped_existing`.

If false, build the schema from enabled note types and frontmatter style:

```yaml
note_types:
  permanent:
    required: [created, type, tags]
    optional: [updated, status, source, last_reviewed, epistemic_status, confidence]
    allowed_values:
      status: [draft, evergreen, archived]
      type: [permanent]

  fleeting:
    required: [created, type, tags]
    optional: [source, review_after, captured_at, source_type]
    allowed_values:
      type: [fleeting]

  moc:
    required: [created, type]
    optional: [tags, updated]
    allowed_values:
      type: [moc]

  resource:
    required: [created, type]
    optional: [tags, updated, source]
    allowed_values:
      type: [resource]

  project:
    required: [created, type]
    optional: [tags, updated, status]
    allowed_values:
      status: [active, paused, completed]
      type: [project]

  daily:
    required: [created, type]
    optional: [tags, mood, weather]
    allowed_values:
      type: [daily]

  research:
    required: [created, type, source_type]
    optional: [report_path, captured_at, source, status, tags]
    allowed_values:
      status: [draft, evergreen]
      source_type: [research-report, voice, image, pdf, youtube, screenshot]
      type: [research]
```

Include only the note types the user enabled. If `FrontmatterStyle` is minimal, move `updated`, `status`, `source` from `required` to `optional` (or omit from the schema if they were not in required).

Write to `<vault>/.mz/vault-schema.yml`. Record `SchemaAction: written`.

## Step 4: Write starter templates

Create two template files under `<vault>/99 - Meta/Templates/`:

**Permanent.md:**

```markdown
---
created: {{date}}
type: permanent
tags: []
status: draft
---

# {{title}}

One atomic idea per note. If a second thesis emerges, split into a new note.

## Related

- [[]]
```

**Fleeting.md:**

```markdown
---
created: {{date}}
type: fleeting
tags: [inbox]
---

# {{title}}

Raw capture — promote to permanent or delete within days.
```

If `FrontmatterStyle` is extended, add `updated`, `source`, `epistemic_status` fields to the Permanent template frontmatter.

Skip writing a template if the file already exists. Record `TemplatesWritten: [list]`.

## Step 5: Write .mz/memory/MEMORY.md

If `<vault>/.mz/memory/MEMORY.md` already exists, skip.

Otherwise write:

```markdown
# Project Memory

<!-- Entries below are auto-managed by mz-memory. Most recent first. -->
```

Record `MemoryAction: written|skipped_existing`.

## Step 6: Update state

Update `state.md`:

```yaml
Phase: 1
Status: scaffold_complete
FoldersCreated: [list]
PermanentSubfolders: [list]
CLAUDEAction: written|skipped_existing|appended_missing_sections
SchemaAction: written|skipped_existing
TemplatesWritten: [list]
MemoryAction: written|skipped_existing
```

Return control to SKILL.md Phase 2 for verification.

## Constraints

- Never overwrite any existing file. Check existence before every write.
- Never create `.obsidian/` — that is the Obsidian app's responsibility.
- Never write notes (only templates and governance files). Note creation is for `vault-ingest` and `process-notes`.
- The `{{placeholder}}` syntax in templates is Obsidian Templater/Templates plugin syntax — write it literally, do not resolve it.
- Folder names use the `-` (space-dash-space) separator after the number prefix. This is intentional for Obsidian sidebar readability.

## Common Rationalizations

| Rationalization                                                                 | Rebuttal                                                                                                                                                                |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Create empty placeholder notes in each folder so the user sees the structure." | "Empty notes pollute the vault graph, trigger false positives in health checks, and violate Obsidian convention: create a folder only when it receives its first note." |
| "Write a comprehensive template with every possible frontmatter field."         | "Template-bombing every file with 15 fields trains users to ignore frontmatter. Minimal viable fields, extended only when the user chose extended style."               |
| "Skip .mz/vault-schema.yml — the user can run vault-schema later."              | "Every downstream skill that validates notes reads this file. Missing schema means vault-schema, vault-triage, and process-notes all degrade on first run."             |
