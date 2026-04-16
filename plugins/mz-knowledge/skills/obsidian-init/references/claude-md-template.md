# CLAUDE.md Template for Obsidian Vaults

Lazy-loaded reference for `obsidian-init`. Read this file and substitute `{{PLACEHOLDERS}}` with values from `state.md` interview answers. Do not load into context unless Phase 1 Step 2 needs it.

## Template

The full CLAUDE.md content follows. Copy everything between the `<!-- BEGIN TEMPLATE -->` and `<!-- END TEMPLATE -->` markers, substitute placeholders, and write to `<vault>/CLAUDE.md`.

<!-- BEGIN TEMPLATE -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Not a code repository.** This directory is an Obsidian knowledge vault. `.md` files here are knowledge notes — editing them *is* the product, not documentation for source code. Apply the rules below in place of standard software-repo heuristics.

## Vault Context

- **Type**: Obsidian vault. {{VAULT_PURPOSE}}.
- **Root**: `{{VAULT_ROOT}}`.
- **State**: Initialized {{DATE_TODAY}}. Layout below is the *current* shape — when a later note contradicts this file, trust the note and update CLAUDE.md.
- **Mozg pipelines**: `.mz/` is active. Routing (`using-mozg-pipelines`) and memory hooks (`mz-memory`) run each session. Project memory lives in `.mz/memory/MEMORY.md`.

## Obsidian Syntax — Never "Fix" These

Obsidian extends CommonMark. Do not convert, lint-correct, or flag the following as errors:

- `[[Wikilinks]]`, `[[Target|Alias]]`, `[[Target#Heading]]`, `[[Target#^block-id]]`
- `![[Embed]]` transclusions (notes, images, blocks)
- YAML frontmatter (`---` fenced at file top)
- `#tag`, `#nested/tag` anywhere in body text
- Callouts: `> [!note]`, `> [!warning]`, `> [!contradiction]`, etc.
- Trailing `^block-id` anchors on paragraphs
- ```` ```dataview ```` and ```` ```base ```` code fences

Resolving a `[[wikilink]]`: search the vault for a `.md` whose basename (minus extension) matches. Obsidian resolves by name, not by relative path.

## Folder Layout (PARA + Zettelkasten hybrid)

Numbered prefixes force order in the file explorer. Create a folder only when it receives its first note — no empty scaffolding.

```text
{{FOLDER_LAYOUT}}
```

### `04 - Permanent/` sub-hierarchy

Permanents are nested by topic. Current shape:

```text
{{PERMANENT_HIERARCHY}}
```

New subfolders are encouraged as the library grows — propose when introducing a *top-level* Permanent category, but new second-level subfolders can be added inline when a note fits no existing leaf.

## Note Conventions

- **Filename — baseline rules for every `.md`**

  - **Title Case, space-separated.** Example: `Graph-based threading for audio pipelines.md`.
  - **Hyphens only inside compound concepts.** `Multi-tenant`, `Beat-structure`. Never as word separator.
  - **No underscores. No snake_case. No kebab-case as separator.**
  - **No leading dot** in filenames.
  - **Period `.` forbidden inside filename** except for `.md` extension.
  - **Parens `(...)` for disambiguation**: `MyNote (Context).md`.
  - **Length ≤ 60 characters** including `.md`.

- **Filename — by note type**

  - Daily: `YYYY-MM-DD.md`.
  - Fleeting: `YYYYMMDDHHmm - Title.md` (timestamp + dash + title).
  - Permanent / Resource / MOC: descriptive Title Case, no date.
  - Project folder root: always `Index.md`.

- **Frontmatter** — add fields only when the note needs them:

  ```yaml
  ---
  {{FRONTMATTER_TEMPLATE}}
  ---
  ```

- **Tags**: {{TAG_STYLE_NOTE}}

- **Linking**: any mention of a concept that has (or should have) its own note becomes `[[Wikilink]]`. Creating an empty stub is fine — it collects backlinks from day one.

- **Atomicity**: one idea per Permanent note. If a note sprouts a second thesis, split.

- **Permanent placement**: every Permanent note lives in a topic subfolder, never at the root of `04 - Permanent/`. Pick the narrowest existing leaf; if none fits, add a new leaf subfolder.

## Compounding Wiki Principle

Goal: a graph that gets denser with every source, not a dated pile of standalone captures.

When ingesting a source (paper, article, conversation), do **not** dump it into one note. Extract claims, decisions, and open questions into the relevant existing notes; promote genuinely new ideas into new atomic Permanent notes.

- Before writing a new Permanent note, grep for existing notes on the topic and extend them first.
- When sources disagree, add a `> [!contradiction]` callout citing both and link them. Never silently pick a winner.
- Update the relevant MOC in `00 - MOCs/` whenever you add meaningful notes to its territory.

## Vault-Specific Don'ts

- Do not mass-convert `[[wikilinks]]` ↔ `[text](path.md)` — each form means something distinct to Obsidian.
- Do not strip frontmatter, callouts, or tags because they look non-standard.
- Do not create top-level folders outside the layout above without proposing first.
- Do not delete an orphan note; propose it. Orphans are often drafts or deliberate terminals.
- Do not edit `.obsidian/` config unless the user asks — Obsidian manages that.
- Do not add a toolchain (build, test, lint, typecheck) unless asked.

## Rename Safety Checklist

Filesystem renames done outside the Obsidian UI do **not** auto-update links. When renaming `Old Name.md` → `New Name.md`, grep each link form separately:

1. `\[\[Old Name\]\]` — plain link
1. `\[\[Old Name\|` — aliased link
1. `\[\[Old Name#` — heading link
1. `\[\[Old Name\^` — block ref
1. `!\[\[Old Name` — embed
1. Frontmatter refs (`related: [[Old Name]]`, `source: [[Old Name]]`, etc.)

## Ad-Hoc Vault Health Checks

No build / test / lint is configured. When health checks become recurring, add a script under `99 - Meta/scripts/` rather than installing global tooling.

- **Orphans**: list every `.md` basename, subtract any appearing as `[[name]]` anywhere in the vault.
- **Dead wikilinks**: extract `[[target]]` tokens, flag those without a matching `.md`.
- **Missing frontmatter**: files whose first line is not `---` (if the note type is expected to have it).

## Mozg Skill Routing in This Vault

The routing map from `using-mozg-pipelines` is loaded every session, but most entries target code workflows. Skills useful inside this vault:

- `mz-knowledge:obsidian-init` — bootstrap vault structure (already ran).
- `mz-knowledge:vault-ingest` — capture voice, image, PDF, YouTube into fleeting notes.
- `mz-knowledge:process-notes` — atomize fleeting notes into permanent notes.
- `mz-knowledge:vault-schema` — validate frontmatter against schema rules.
- `mz-knowledge:vault-triage` — batch-process inbox for promote/merge/discard.
- `mz-knowledge:vault-connect` — suggest wikilinks between notes.
- `mz-knowledge:vault-research` — ingest research reports as atomic notes.
- `mz-knowledge:vault-provenance` — classify epistemic status of claims.
- `mz-knowledge:vault-answer` — grounded Q&A against vault content.
- `mz-knowledge:vault-refactor` — safe bulk renames with link updates.
- `mz-knowledge:vault-review` — periodic review of permanent notes.
- `mz-knowledge:vault-health` — orphan/dead-link/frontmatter checks.
- `mz-dev-base:deep-research` — multi-source research to seed new notes.
- `mz-creative:brainstorm` — multi-perspective ideation on a vault topic.

Skip code-shaped skills (`build`, `debug`, `audit`, `verify`, `optimize`, `review-branch`, `review-pr`, `scan-prs`) — this is not a code repo.

<!-- END TEMPLATE -->

## Placeholder Reference

| Placeholder                | Source                                                    | Example                                                        |
| -------------------------- | --------------------------------------------------------- | -------------------------------------------------------------- |
| `{{VAULT_PURPOSE}}`        | `VaultPurpose` from state.md                              | `Personal second brain for AI and engineering knowledge`       |
| `{{VAULT_ROOT}}`           | `Vault` from state.md (absolute path)                     | `/home/user/Obsidian/MyVault`                                  |
| `{{DATE_TODAY}}`           | Current date                                              | `2026-04-16`                                                   |
| `{{FOLDER_LAYOUT}}`        | Folders created in Step 1, formatted as the numbered list | See default layout in scaffold_vault.md                        |
| `{{PERMANENT_HIERARCHY}}`  | `PrimaryTopics` formatted as tree under `04 - Permanent/` | `04 - Permanent/\n├── AI/\n├── Engineering/\n└── Business/`    |
| `{{FRONTMATTER_TEMPLATE}}` | Based on `FrontmatterStyle`                               | `created: YYYY-MM-DD\ntype: {{NOTE_TYPES_LIST}}\ntags: []`     |
| `{{TAG_STYLE_NOTE}}`       | Based on `TagStyle`                                       | `hierarchical with /: #ai/llm, #status/draft`                  |
| `{{NOTE_TYPES_LIST}}`      | Pipe-separated enabled types                              | `permanent \| fleeting \| moc \| resource \| project \| daily` |
