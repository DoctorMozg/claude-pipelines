# mz-knowledge

Full lifecycle management for a personal Obsidian knowledge vault — bootstrap, capture, atomize, triage, link, review, and query.

## What it does

Provides 15 skills and 11 agents that cover every stage of a knowledge base: bootstrapping vault structure, capturing multimodal input (voice, image, PDF, YouTube), atomizing raw captures into permanent notes, triaging the inbox, suggesting wikilinks, validating frontmatter schemas, reviewing notes for staleness, grounded Q&A against vault content, and safe bulk refactoring with rollback.

Every skill reads the vault's `CLAUDE.md` for conventions (folder layout, frontmatter schema, tag taxonomy) and writes state to `.mz/task/`. User approval gates prevent any vault write without explicit sign-off.

## Skills

### Bootstrap

| Skill             | Command                       | What it does                                                      |
| ----------------- | ----------------------------- | ----------------------------------------------------------------- |
| **obsidian-init** | `/obsidian-init <vault path>` | Interview → scaffold PARA+Zettelkasten folders, CLAUDE.md, schema |

### Capture & Processing

| Skill              | Command                         | What it does                                                |
| ------------------ | ------------------------------- | ----------------------------------------------------------- |
| **vault-ingest**   | `/vault-ingest <path or URL>`   | Detect modality → transcribe/OCR → approval → fleeting note |
| **process-notes**  | `/process-notes <note path>`    | Atomize fleeting → permanent notes with frontmatter + links |
| **vault-research** | `/vault-research <report path>` | Parse research report → atomic notes + link suggestions     |

### Vault Maintenance

| Skill              | Command                         | What it does                                                 |
| ------------------ | ------------------------------- | ------------------------------------------------------------ |
| **vault-triage**   | `/vault-triage`                 | Batch-score inbox → promote / merge / discard / defer        |
| **vault-schema**   | `/vault-schema [validate]`      | Validate frontmatter against YAML schema, propose migrations |
| **vault-connect**  | `/vault-connect <note path>`    | Suggest `[[wikilinks]]` between notes                        |
| **vault-refactor** | `/vault-refactor <rename spec>` | Safe bulk renames with link-graph updates and rollback       |
| **vault-review**   | `/vault-review`                 | Periodic review of permanent notes for staleness             |
| **vault-health**   | `/vault-health`                 | Orphan detection, dead wikilinks, missing frontmatter        |

### Analysis & Query

| Skill                | Command                         | What it does                                        |
| -------------------- | ------------------------------- | --------------------------------------------------- |
| **vault-provenance** | `/vault-provenance <note path>` | Classify claims by epistemic status                 |
| **vault-answer**     | `/vault-answer <question>`      | Grounded Q&A with inline `[[citations]]` from vault |

### Reference

| Skill                 | Command              | What it does                                         |
| --------------------- | -------------------- | ---------------------------------------------------- |
| **obsidian-bases**    | `/obsidian-bases`    | Bases `.base` file syntax (filters, formulas, views) |
| **obsidian-markdown** | `/obsidian-markdown` | Obsidian-flavored markdown syntax reference          |
| **obsidian-cli**      | `/obsidian-cli`      | Obsidian URI scheme and CLI reference                |

## Pipeline

```
/obsidian-init ~/Obsidian/MyVault
  │
  ├─ Interview: purpose, topics, note types, frontmatter style, tags
  ├─ Approval gate: scaffold plan
  └─ Scaffold: folders, CLAUDE.md, .mz/vault-schema.yml, templates

/vault-ingest ~/recordings/meeting.m4a
  │
  ├─ Phase 1: Detect voice → check whisper → dispatch capture-normalizer
  ├─ Phase 1.5: Approval gate — verbatim transcript
  └─ Phase 2: Write fleeting note → inbox/

/vault-triage
  │
  ├─ Phase 0: Read vault CLAUDE.md, glob inbox, create batch (≤7 notes)
  ├─ Phase 1: Dispatch triage-scorer → promote/merge/discard/defer
  ├─ Phase 1.5: Approval gate — batch decisions
  └─ Phase 2: Execute decisions (move, merge, delete, defer)

/vault-research .mz/research/research_2026_04_17_topic.md
  │
  ├─ Phase 1: Parse report → classify sections → partition into ≤450-word windows
  ├─ Phase 1.5: Approval gate — window boundaries
  ├─ Phase 2: Sequential atomization-proposer dispatches → merged proposals
  ├─ Phase 2.5: Approval gate — note proposals
  ├─ Phase 3: Write permanent notes → dispatch link-suggester
  ├─ Phase 3.5: Approval gate — link suggestions
  └─ Phase 3 (cont): Apply approved links
```

## Agents

| Agent                    | Model  | Role                                                |
| ------------------------ | ------ | --------------------------------------------------- |
| `capture-normalizer`     | sonnet | Transcription/OCR dispatch for vault-ingest         |
| `triage-scorer`          | haiku  | Deterministic heuristic scoring for inbox notes     |
| `atomization-proposer`   | opus   | Splits content into atomic note proposals           |
| `link-suggester`         | sonnet | Scans vault for wikilink candidates between notes   |
| `provenance-tracer`      | sonnet | Classifies claims by epistemic origin               |
| `schema-validator`       | haiku  | Validates frontmatter against vault-schema.yml      |
| `vault-query-answerer`   | sonnet | Searches vault and synthesizes cited answers        |
| `vault-refactor-scanner` | sonnet | Builds link graph and identifies affected files     |
| `vault-refactor-writer`  | sonnet | Applies renames with link updates and rollback file |
| `vault-audit-collector`  | haiku  | Collects orphans, dead links, missing frontmatter   |
| `moc-gap-detector`       | haiku  | Finds permanent notes missing from their topic MOC  |

## Output location

Skills write state and intermediate artifacts to `.mz/task/<skill>_<slug>_<HHMMSS>/`. Vault notes are written to the vault's folder structure as defined in CLAUDE.md.

## Install

```bash
claude plugin install mz-knowledge
```

## Usage

```bash
# Bootstrap a new vault
/obsidian-init ~/Obsidian/MyVault

# Capture a voice memo
/vault-ingest ~/recordings/standup.m4a

# Process the inbox
/vault-triage

# Ask a question grounded in vault content
/vault-answer "what did I capture about API gateway layering?"

# Validate all frontmatter
/vault-schema validate
```
