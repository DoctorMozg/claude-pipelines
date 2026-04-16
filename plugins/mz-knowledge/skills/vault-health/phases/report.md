# Phase 2: Write Audit Note

## Goal

Write `_vault_audit_YYYY-MM-DD.md` to the vault root.

## Audit note format

File: `<vault_path>/_vault_audit_<YYYY-MM-DD>.md`

```markdown
---
date: <YYYY-MM-DD>
type: vault-audit
tags: [vault-health]
---

# Vault Health Audit — <YYYY-MM-DD>

## Summary

| Metric | Count | Target |
|--------|-------|--------|
| Orphan notes | N | < 5% of total |
| Broken wikilinks | N | 0 |
| Stub notes (<100w) | N | < 10% of total |
| Stale notes (>90d) | N | — |
| Singleton tags | N | — |

## Orphan Notes (no backlinks)

...list...

## Broken Wikilinks

...list...

## Stub Notes

...list...

## Stale Notes

...list...

## Tag Report

Total unique tags: N
Singleton tags: N
Top tags: ...

## Next Steps

- [ ] Review and link or archive orphan notes
- [ ] Fix broken wikilinks
- [ ] Expand or delete stub notes
```

## After writing

1. Update `state.md`: `Status: completed`, `Phase: 2`, `Completed: <ISO timestamp>`.
1. Print: `Audit written to <vault_path>/_vault_audit_<date>.md — N orphans, N broken links, N stubs.`

## Error handling

- **Vault root unwritable** → escalate via AskUserQuestion; do not write the audit note to an alternate location without explicit user direction.
- **Audit file already exists for today** → append `_v2`, `_v3` suffix and note the collision in `state.md`.
- **Collector data file missing or corrupt at write time** → stop, mark `Status: blocked` in `state.md`, and escalate via AskUserQuestion.
