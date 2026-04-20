---
name: vault-health
description: 'ALWAYS invoke when auditing an Obsidian vault for orphan notes, broken links, stale content, stub notes, or tag inconsistencies. Triggers: vault audit, orphan notes, broken wikilinks, vault health check.'
argument-hint: '[vault path or leave empty to use OBSIDIAN_VAULT_PATH env]'
model: sonnet
allowed-tools: Agent, Bash, Read, Glob, Grep, Write, AskUserQuestion
---

## Overview

Discipline skill that audits an Obsidian vault and produces a structured `_vault_audit_YYYY-MM-DD.md` health note at the vault root. Checks: orphan notes (zero backlinks), broken wikilinks, stub notes (\<100 words, zero outlinks), stale notes (mtime >90 days + zero outlinks), and tag inconsistencies. Uses the official `obsidian` CLI when available, falls back to file scanning.

## When to Use

Invoke for weekly vault maintenance, before a knowledge review session, or after large imports. Trigger phrases: "vault audit", "orphan notes", "broken wikilinks", "vault health check".

### When NOT to use

- Fixing the issues found — use `process-notes` or `vault-connect` after the audit.
- Semantic search or note retrieval — this skill only inventories health, it does not answer content queries.

## Constants

- **TASK_DIR**: `.mz/task/`
- **AUDIT_NOTE_PREFIX**: `_vault_audit_`
- **STUB_WORD_THRESHOLD**: 100
- **STALE_DAYS**: 90

## Arguments

`$ARGUMENTS` is an optional vault path. If empty, resolve from `OBSIDIAN_VAULT_PATH` env, then `MZ_VAULT_PATH` env. If none are set, ask via AskUserQuestion.

## Core Process

### Phase Overview

| Phase | Goal          | Details             |
| ----- | ------------- | ------------------- |
| 0     | Setup         | Inline below        |
| 1     | Collect       | `phases/collect.md` |
| 1.5   | User approval | Inline below        |
| 2     | Write audit   | `phases/report.md`  |

### Phase 0: Setup

1. Resolve vault path from `$ARGUMENTS`, then `OBSIDIAN_VAULT_PATH`, then `MZ_VAULT_PATH`.
1. If no vault path resolved, escalate via AskUserQuestion — never guess.
1. `task_name` = `<YYYY_MM_DD>_vault-health_<vault-slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<vault-slug>` is a snake_case summary of the vault directory name (max 20 chars); on same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Vault: <resolved path>`.
1. Emit a visible setup block showing `task_name`, resolved vault path, and working dir.

### Phase 1 — Collect

See `phases/collect.md`.

### Phase 1.5: User approval gate

**This orchestrator** (not a subagent) must present findings to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before presenting, Read `.mz/task/<task_name>/audit_data.md` in full. Present the full verbatim summary from `audit_data.md`. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Before invoking AskUserQuestion, emit a text block to the user:

```
**Vault Health Findings Ready**
Your vault has been scanned for orphans, broken links, stubs, stale notes, and tag inconsistencies.

- **Approve** → proceed to Phase 2 (write audit report to vault)
- **Reject** → abort without writing, task marked cancelled
- **Feedback** → describe changes you want; Phase 1 re-runs with your input, then return here
```

Use AskUserQuestion with:

```
Vault health findings ready. Please review:

- Orphans: N
- Broken wikilinks: N
- Stubs: N
- Stale: N
- Tags: N unique, N singletons

Type **Approve** to proceed, **Reject** to cancel, or type your feedback.
```

**Response handling**:

- **"approve"** → update state, proceed to Phase 2 (write report).
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → adjust what to include (narrow a check, drop a category, re-run a collector), re-run Phase 1 if needed, then return to this gate and re-present **via AskUserQuestion** using the same format. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 2 without explicit approval.

### Phase 2 — Write audit

See `phases/report.md`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                        | Rebuttal                                                                                                                                     |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| "I can see the issues in my head, skip the audit note" | "The audit note is the log. Without it, patterns across weeks are invisible and you redo the same checks next week."                         |
| "Only run the fast checks, skip stale detection"       | "Stale notes are the silent knowledge rot. Skipping them is how 47% of captures never get processed."                                        |
| "Auto-fix the orphans without asking"                  | "An orphan may be intentionally isolated (inbox item, template). Auto-delete creates irreversible data loss — always surface before acting." |

## Red Flags

- Reporting results without writing an audit note (no log means no pattern detection over time).
- Auto-fixing broken links without showing what they were (breaks provenance).
- Skipping the approval gate and writing directly.

## Verification

Confirm `_vault_audit_YYYY-MM-DD.md` was written to the vault root. Print the orphan count and broken link count from the written audit.

## Error Handling

- **Vault path missing or invalid** → escalate via AskUserQuestion; never guess a default.
- **Obsidian CLI unavailable** → fall back to file scanning via Bash/Glob/Grep; record the fallback in `state.md`.
- **Empty collector result** (agent returns nothing) → retry once with a clarified prompt; if still empty, note the gap in `state.md` and escalate via AskUserQuestion before writing.
- Never guess — on any ambiguity (ambiguous vault path, missing tooling, conflicting results) escalate via AskUserQuestion rather than fabricate.
