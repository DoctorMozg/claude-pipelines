# Phase 1: Collect Vault Health Data

## Goal

Run all health checks and collect structured findings into `.mz/task/<task_name>/audit_data.md`.

## Actions

### 1. Dispatch `vault-audit-collector` agent

Dispatch the `vault-audit-collector` agent with this task-specific prompt:

```
Vault path: <vault_path>
Task dir: .mz/task/<task_name>/

Run all vault health checks and write findings to .mz/task/<task_name>/audit_data.md.

Checks to run:

1. Orphan notes — notes with zero backlinks (no other note links to them).
   - Use `obsidian orphans` CLI if available, else scan all .md files for wikilinks.
   - List up to 20 orphans with path and word count.

2. Broken wikilinks — wikilinks in notes that do not resolve to an existing file.
   - Use `obsidian unresolved` CLI if available.
   - List up to 20 broken links with source note and target.

3. Stub notes — notes with <100 words AND zero outgoing wikilinks AND mtime >30 days.
   - Scan .md files, count words (exclude frontmatter), check outlinks.
   - List up to 15 stubs with path and word count.

4. Stale notes — notes not modified in >90 days with zero outgoing wikilinks.
   - Check file mtime, scan for [[wikilinks]] in content.
   - List up to 15 stale notes with path and days-since-modified.

5. Tag statistics — unique tag count, tags used only once (singletons).
   - Use `obsidian tags` CLI if available, else grep frontmatter.
   - Report: total unique tags, singleton count, top 10 most-used tags.

Output format in audit_data.md:

    vault_path: <path>
    checked_at: <ISO timestamp>
    orphans:
      count: N
      sample: [list of paths]
    broken_links:
      count: N
      sample: [list of {source, target}]
    stubs:
      count: N
      sample: [list of {path, word_count}]
    stale:
      count: N
      sample: [list of {path, days_since_modified}]
    tags:
      total_unique: N
      singletons: N
      top_10: [list]

STATUS: DONE with findings written to audit_data.md, or BLOCKED if the vault is not accessible.
```

### 2. After the agent completes

Read `.mz/task/<task_name>/audit_data.md`. Update `state.md`: `Status: collection_complete`, `Phase: 1`.

### 3. Present findings for approval

Format the counts from `audit_data.md` for the Phase 1.5 approval gate defined in `SKILL.md`. Do not proceed to Phase 2 until the user explicitly approves.

## Error handling

- **Agent returns empty or malformed `audit_data.md`** → retry the dispatch once with a clarified prompt. If still empty, note the gap in `state.md` and escalate via AskUserQuestion before the approval gate.
- **Obsidian CLI missing** → record the fallback to file-scan mode in `state.md` and proceed — the collector should still produce findings via Bash/Glob/Grep.
- **Vault path unreadable** → escalate via AskUserQuestion; never guess a substitute path.
