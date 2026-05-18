---
name: obsidian-init
description: ALWAYS invoke when bootstrapping a new Obsidian vault with CLAUDE.md, folder structure, schema, and rules. Triggers init vault, bootstrap obsidian, setup knowledge base, create vault structure.
argument-hint: <vault path> [--minimal]
model: sonnet
allowed-tools: Agent, Read, Write, Bash, Grep, Glob, AskUserQuestion
---

# Obsidian Init

## Overview

Discipline skill that bootstraps a new Obsidian vault (or retrofits an existing one) with a CLAUDE.md governance file, PARA+Zettelkasten folder structure, `.mz/vault-schema.yml`, and starter templates. The output is a vault ready for all other mz-knowledge skills — `process-notes`, `vault-ingest`, `vault-schema`, `vault-triage`, `vault-connect`, etc.

## When to Use

- Setting up a new Obsidian vault from scratch for use with Claude Code.
- Retrofitting an existing vault that lacks CLAUDE.md or `.mz/` structure.

### When NOT to use

- Vault already has well-formed CLAUDE.md and `.mz/vault-schema.yml` — edit directly.
- Processing or ingesting notes — use `vault-ingest`, `process-notes`.

## Constants

- **TASK_DIR**: `.mz/task/` | **SCHEMA_PATH**: `.mz/vault-schema.yml` | **CLAUDE_MD_PATH**: `CLAUDE.md` (vault root)

## Core Process

| Phase | Goal                          | Details                    |
| ----- | ----------------------------- | -------------------------- |
| 0     | Setup + interview             | Inline below               |
| 0.5   | User approval — scaffold plan | Inline below               |
| 1     | Scaffold vault                | `phases/scaffold_vault.md` |
| 2     | Verify                        | Inline below               |

### Phase 0: Setup + Interview

1. Parse `$ARGUMENTS`. First argument is the vault path. If `--minimal` flag is present, skip interview and use defaults.
1. If the vault path is empty, ask via AskUserQuestion.
1. Check whether the path exists. If it does, scan for existing `.obsidian/`, `CLAUDE.md`, `.mz/`, and any folder structure. Record findings — the skill must not destroy existing content.
1. Derive `task_name = <YYYY_MM_DD>_obsidian-init_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<slug>` is a snake_case summary of the vault directory name (max 20 chars); on same-day collision append `_v2`, `_v3`. Create `TASK_DIR<task_name>/`.
1. Write `state.md` with `schema_version: 2`, `Status: running`, `Phase: 0`, `Started`, `Vault`, `ExistingCLAUDE: true|false`, `ExistingSchema: true|false`, `ExistingFolders: [list]`, `phase_complete: false`, `what_remains: []`.

Unless `--minimal` was passed, ask the user via AskUserQuestion (single question, all items):

- question:
  ```
  Vault bootstrap interview for <vault path>.

  1. Vault purpose — what kind of knowledge? (e.g., "personal second brain", "team engineering wiki", "research notes")
  2. Primary topics — 3-5 top-level categories for permanent notes (e.g., AI, Engineering, Business)
  3. Note types — which do you use? (permanent, fleeting, daily, moc, resource, project — all enabled by default)
  4. Frontmatter style — minimal (created, type, tags) or extended (+ updated, status, source, epistemic_status)?
  5. Tag taxonomy — flat (#ai, #engineering) or hierarchical (#ai/llm/claude, #status/draft)?

  Or choose one of the quick options below.
  ```
- options:
  - **Defaults** — accept all defaults (personal second brain, AI/Engineering/Business/Career topics, all six note types, extended frontmatter, hierarchical tags)
  - **Minimal** — bare structure only, no interview answers applied

Record answers (or the chosen option) in `state.md` under `VaultPurpose`, `PrimaryTopics`, `NoteTypes`, `FrontmatterStyle`, `TagStyle`.

### Phase 0.5: User Approval — Scaffold Plan

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

Build the plan from interview answers (or defaults). Write the scaffold plan to `.mz/task/<task_name>/scaffold_plan.md` so it can be read and re-emitted on each loop iteration.

**Pre-read**: Read `.mz/task/<task_name>/scaffold_plan.md` and capture the full contents into context.

**Surface 1 — emit the plan message.** Output the scaffold plan verbatim as a normal markdown chat message:

```
## Scaffold plan ready for review — obsidian-init

Scaffold plan for <vault path>:

Folders to create:
<numbered list of folders with descriptions>

Files to write:
- CLAUDE.md — vault governance (~150 lines)
- .mz/vault-schema.yml — frontmatter schema for vault-schema skill
- .mz/memory/MEMORY.md — project memory index (empty)
- 99 - Meta/Templates/Permanent.md — starter template
- 99 - Meta/Templates/Fleeting.md — starter template

<if existing content detected>
Existing content preserved:
- <list of files/folders that will NOT be overwritten>
</if>

---
**Approve** → proceed to Phase 1, write all scaffolding files  ·  **Reject** → abort the task, no files created  ·  reply with feedback to revise
```

Emit the full verbatim contents of `.mz/task/<task_name>/scaffold_plan.md` — do not substitute a path, summary, or placeholder.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the plan in the question body, it lives in the plan message above:

- question: `The scaffold plan above is ready for review.`
- options:
  - **Approve** — proceed to Phase 1 and write all scaffolding files
  - **Reject** — abort the task, no files will be created

Response handling:

- **Approve** → update state to `plan_approved`, proceed to Phase 1.
- **Reject** → update state to `aborted_by_user` and stop. Do not proceed.
- **Any other reply (feedback)** → adjust the plan, overwrite `.mz/task/<task_name>/scaffold_plan.md`, return to this gate, re-read the updated plan, and re-emit the entire plan message from scratch. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 1 without explicit approval.

### Phase 1: Scaffold Vault

Create folders, write CLAUDE.md, schema, and templates. See `phases/scaffold_vault.md`.

### Phase 2: Verify

1. Glob `<vault>/**/*.md` and `<vault>/.mz/**` to confirm all planned files exist.
1. Read `CLAUDE.md` and verify it contains: Vault Context, Obsidian Syntax, Folder Layout, Note Conventions, Frontmatter, Compounding Wiki Principle, Don'ts sections.
1. Read `.mz/vault-schema.yml` and verify YAML parses with `note_types:` key.
1. Confirm no existing files were overwritten (compare against Phase 0 scan).

Update `state.md` to terminal: `Status: complete`, `Phase: 2`, `Completed: <ISO>`.

## Techniques

Techniques: delegated to `phases/scaffold_vault.md` — template content lives in `references/claude-md-template.md` (lazy-loaded).

## Common Rationalizations

| Rationalization                                                | Rebuttal                                                                                                                                                                                       |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Just copy the example CLAUDE.md verbatim — it's good enough." | "Every vault has different topics, note types, and conventions. A copied CLAUDE.md with someone else's topic hierarchy misleads every downstream skill that reads it."                         |
| "Skip the interview — defaults work for everyone."             | "Defaults work for the author's vault. A team wiki needs different folder layout, frontmatter fields, and tag conventions. The interview costs 30 seconds and prevents hours of retrofitting." |
| "Overwrite the existing CLAUDE.md — ours is better."           | "The existing CLAUDE.md may contain vault-specific rules accumulated over months. Merge, don't replace. If the user wants a clean slate, they say so explicitly."                              |

## Red Flags

- Writing CLAUDE.md without checking whether one already exists.
- Creating folders for note types the user disabled.
- Hardcoding topic names from the example vault instead of using user's answers.
- Writing to `.obsidian/` — that directory belongs to the Obsidian app.

## Verification

Print this block before concluding:

```
obsidian-init verification:
  [ ] Interview completed (or --minimal/defaults accepted)
  [ ] Scaffold plan approved via AskUserQuestion before any writes
  [ ] CLAUDE.md written with vault-specific content (not a generic copy)
  [ ] .mz/vault-schema.yml written with note_types matching user's chosen types
  [ ] Folder structure created matching approved plan
  [ ] No existing files overwritten
  [ ] state.md Status is `complete` with Completed timestamp
```

If any box is unchecked, report the failure explicitly.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.
