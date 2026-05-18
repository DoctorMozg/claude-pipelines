# Resume Protocol — Entry Contract

Canonical contract for resuming a mz-dev-pipe skill from a previously-written `.mz/task/<task_name>/state.md`. The state file is the load-bearing checkpoint that survives context compaction; this protocol is how skills actually use it as an entry point, not just a write-only audit log.

## When a skill enters

Every mz-dev-pipe skill, in its Phase 0 setup, MUST:

1. **Compute the candidate task name** from `$ARGUMENTS` per the skill's naming convention (`<YYYY_MM_DD>_<skill>_<slug>`, with `_v2`, `_v3` collision suffixes).
1. **Check for an existing state file** at `.mz/task/<candidate_task_name>/state.md`.
1. **Branch on what is found**:
   - **No file** → fresh task. Proceed with normal Phase 0 setup (create directory, write new state file with `schema_version: 2`, `phase_complete: false`, `what_remains: []`).
   - **File exists with `Status: complete` or `Status: aborted_by_user`** → finished task. Auto-suffix `_v2` / `_v3` and proceed as fresh task. Log the suffix bump to chat.
   - **File exists with `Status: running` or `Status: failed`** → in-progress or interrupted task. Present the **Resume gate** below.

## Resume gate

This gate is a variant approval gate — it presents the existing task state and offers three named actions. It follows the two-surface plan pattern in `shared/approval-gate.md`.

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read the existing `.mz/task/<task_name>/state.md` in full and capture its contents into context. Validate `schema_version` per `shared/state-schema.md` mismatch policy first — if the schema is unrecognized, that error path takes precedence.

**Surface 1 — emit the plan message.** Output the existing state verbatim as a normal markdown chat message. Emit the full verbatim contents of `state.md` — do not substitute a path, summary, or placeholder. Structure:

```
## Existing task found — <skill>

Task `<task_name>` is at Phase <N> (<PhaseName>) with Status: <status>. Last update: <Started or last-modified>. The recorded phase is <complete|incomplete> (`phase_complete: <bool>`); outstanding work: <`what_remains` items, or "none">.

<verbatim state.md contents>

---
**Resume** → re-enter using the existing artifacts (advance past Phase <N> if `phase_complete` is true, else re-run Phase <N> from its idempotent entry point)  ·  **Restart** → archive the old task and start fresh  ·  **New** → leave the old task untouched and create `<task_name>_v2`
```

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the state in the question body, it lives in the plan message above:

- question: `A previous task with this name exists. Choose how to proceed.`
- options:
  - **Resume** — continue from the recorded phase using the existing artifacts
  - **Restart** — archive the old task and start fresh
  - **New** — keep the old task untouched, create a `_v2`

## Response handling

- **Resume** → load the recorded `Phase`, `phase_complete`, `what_remains`, `Iteration`, `FilesWritten`, and any skill-specific keys. If `phase_complete` is true, jump to the next phase's entry point; if false, re-enter the recorded phase. The skill's phase files MUST document their own re-entry rule (see "Phase idempotency" below).
- **Restart** → rename the existing `.mz/task/<task_name>/` directory to `.mz/task/<task_name>_archived_<YYYY_MM_DD_HHMMSS>/`, create a fresh `.mz/task/<task_name>/`, and proceed as a fresh task. Log the archive path to chat.
- **New** → leave the existing directory untouched, suffix `_v2` (or `_v3`, etc.) on the candidate name, create the suffixed directory, proceed as fresh.
- **`MZ_DEV_PIPE_AUTO_APPROVE=1`** in unattended mode → default to **Resume** if the file is `running`, default to **Restart** if `failed`. Log the auto-decision to `state.md` under `## Auto-decisions`. Never auto-overwrite a `complete` or `aborted_by_user` file — those always force a fresh `_vN` suffix.

## Phase idempotency

A skill is resumable only if every phase's writes are re-runnable without corrupting prior output. Phases MUST follow these rules:

1. **Append-only writes**. Phases that build artifacts incrementally (e.g., `FilesWritten` lists, multi-wave coder output) MUST append, never truncate. Re-entering the phase appends from the recorded position.
1. **Idempotent file writes**. A phase that writes a single artifact (e.g., `research.md`, `plan.md`) MAY overwrite the file on re-entry. The skill MUST document this behavior in the phase file.
1. **No external side effects mid-phase**. Phases that send network requests, post comments to GitHub, or otherwise affect external state MUST checkpoint to `state.md` BEFORE the side effect. On re-entry, skip side effects already recorded.
1. **Counter restoration**. Phases with iteration counters (`MAX_FIX_ITERATIONS`, `MAX_REVIEW_ITERATIONS`) MUST read the counter from `state.md` on re-entry. Do not reset to zero.

If a phase cannot meet these rules, the skill MUST mark it non-resumable in its phase file and the resume gate MUST refuse to re-enter at that phase — instead offering only **Restart** and **New**.

## What lives where

- **`shared/state-schema.md`** — defines what `state.md` must contain for any skill to read it.
- **`shared/resume-protocol.md`** (this file) — defines what to do with an existing `state.md` at skill entry.
- **`shared/approval-gate.md`** — defines the AskUserQuestion two-surface pattern that the resume gate uses.

A skill that wires up resume MUST reference all three.

## Why this exists

The `.mz/task/<task_name>/state.md` file already records every checkpoint a skill needs to resume. But until a skill actually reads it on entry, the file is a write-only audit log — useful for forensics, useless for recovery. The 5-lens expert panel called this "structurally promised but operationally absent" and made it a 1.0 ship-blocker.

This protocol is the operational realization of the structural promise. Without it, every context-compacted run is a restart from zero, which silently trains users into a "trust but verify" posture across the whole plugin.
