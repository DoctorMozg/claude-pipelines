---
name: vault-provenance
description: "ALWAYS invoke when classifying epistemic status of claims in a note, back-filling sources frontmatter, or auditing a note's knowledge provenance. Triggers: epistemic status, provenance, claim sources, mark claims."
argument-hint: <note name or path>
model: sonnet
allowed-tools: Agent, Read, Write, Grep, AskUserQuestion
---

# Vault Provenance

## Overview

Discipline skill that classifies every factual claim in a single vault note against a five-value epistemic vocabulary (`first-hand | cited | inferred | received | unmarked`) and back-fills the note's `epistemic_status:` and `sources: []` frontmatter after explicit user approval. Scope is strictly per-note — never vault-wide. Body content is preserved verbatim unless the user opts into annotation mode.

## When to Use

Invoke after drafting a research note, while auditing received-wisdom claims, or before promoting a note to `evergreen`. Trigger phrases: "classify claims in <note>", "back-fill sources for <note>", "audit provenance of <note>".

### When NOT to use

- Vault-wide provenance audits — this skill is per-note by design.
- Suggesting new links between notes — use `vault-connect`.
- Atomizing a note into smaller notes — use `process-notes`.
- Schema or frontmatter compliance checks — use `vault-schema`.

## Arguments

`$ARGUMENTS` is `<note name or path>`. If the argument is a bare name, resolve it against the vault by exact filename match first, then by case-insensitive basename match. If the argument is missing or matches zero / multiple notes, escalate via AskUserQuestion — never guess.

## Constants

- **TASK_DIR**: `.mz/task/`
- **MAX_CLAIMS_PER_NOTE**: 25 — hard cap delegated to `provenance-tracer`; if more claims exist, the first 25 are classified and the cap is flagged in the summary.
- **EPISTEMIC_VOCAB**: `[first-hand, cited, inferred, received, unmarked]` — closed set; no other values.

## Core Process

### Phase Overview

| Phase | Goal                            | Details                      |
| ----- | ------------------------------- | ---------------------------- |
| 0     | Setup                           | Inline below                 |
| 1     | Scan claims                     | `phases/scan_claims.md`      |
| 1.5   | User approval — classifications | Inline below                 |
| 2     | Back-fill sources               | `phases/backfill_sources.md` |

### Phase 0: Setup

1. Parse `$ARGUMENTS` as `<note name or path>`.
1. Resolve the note: if the argument is an absolute path, use it; if a relative path or bare name, resolve against the vault. If zero or multiple matches, escalate via AskUserQuestion with the candidate list. Never guess.
1. Derive `task_name = vault-provenance_<slug>_<HHMMSS>` where `<slug>` is the note basename normalised to `[a-z0-9-]`. Create `TASK_DIR<task_name>/` on disk.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `NotePath: <absolute path>`, `TaskName: <task_name>`.
1. Print a visible setup block showing `task_name`, resolved note path, and the output artifact path `.mz/task/<task_name>/claims_analysis.md`.

### Phase 1 — Scan claims

See `phases/scan_claims.md`.

### Phase 1.5: User approval — classifications

**This orchestrator** (not a subagent) must present findings to the user via AskUserQuestion. This step is interactive and must not be delegated.

Before invoking AskUserQuestion, Read `.mz/task/<task_name>/claims_analysis.md` in full and capture its entire contents.

Present the full verbatim contents of `claims_analysis.md` — each claim with its proposed classification, confidence hint, and suggested sources. Do not substitute a path, summary, or placeholder for the artifact content — present the full verbatim text.

Invoke AskUserQuestion with the verbatim artifact body followed by a prompt ending literally with `Reply 'approve' to proceed, 'reject' to abort, or provide feedback for changes.`

**Response handling**:

- **"approve"** → update state to `classifications_approved`, proceed to Phase 2.
- **"reject"** → update state to `aborted_by_user` and stop. No frontmatter write occurs.
- **Feedback** → incorporate edits (e.g., "reclassify claim 3 as received", "swap proposed source on claim 7", "enable annotation mode"), re-dispatch `provenance-tracer` if a full re-scan is needed or edit the artifact in place for targeted changes, return to this gate and re-present **via AskUserQuestion** (same format, full re-presentation — never diff-only, never summary-only). This is a loop — repeat until the user explicitly approves.

### Phase 2 — Back-fill sources

See `phases/backfill_sources.md`.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                                                     | Rebuttal                                                                                                                                                                                              |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "This note is obviously first-hand — skip the analysis."            | "First-hand classification requires tracing each claim to a direct experiential marker; skipping the analysis produces a false confidence marker across every sentence in the note."                  |
| "Classify all claims at the note level, not per-claim."             | "Note-level classification loses provenance granularity; a single note routinely mixes first-hand observation, cited findings, and inferred conclusions. Every claim must carry its own attribution." |
| "Sources frontmatter is optional — the user probably won't use it." | "Provenance is the whole point of this skill; the frontmatter-only annotation contract is the default output. Treating it as optional silently reduces the skill to an advisory pass."                |
| "Inline annotations are more visible — patch the body by default."  | "Body annotations mutate author-authored prose and can break formatted notes; they require explicit opt-in during the Phase 1.5 feedback loop. Frontmatter-only is the default for a reason."         |

## Red Flags

Red Flags: delegated to phase files — see Phase Overview table above.

## Verification

Verification: delegated to phase files — see Phase Overview table above.
