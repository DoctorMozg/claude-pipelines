# State File Schema — v2 (Canonical)

Canonical authoring spec for the `.mz/task/<task_name>/state.md` checkpoint file. `state.md` is the load-bearing record that survives context compaction — it lets a skill resume mid-task instead of restarting from zero.

This file is **repo-level and authoring-only**. It is not shipped inside an installed plugin (`guidelines/` does not travel with `claude plugin marketplace add`), so no skill reads it at runtime. It is the source authors copy from:

- **mz-dev-pipe** mirrors the full spec in `plugins/mz-dev-pipe/skills/shared/state-schema.md`; its skills reference that local copy at runtime.
- **Every other plugin** embeds the Compact inline contract (below) directly in each skill's `SKILL.md` State Management section — there is no per-plugin schema file.

When this canonical changes, update the mz-dev-pipe mirror and re-check the inline copies.

## Required keys (schema v2)

Every `state.md` MUST contain these top-level keys:

| Key              | Type                 | Required | Purpose                                                                                                                                                                                                                       |
| ---------------- | -------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | integer              | yes      | Schema major version. Currently `2`. First line of the file; never changed after creation.                                                                                                                                    |
| `Status`         | enum                 | yes      | `pending` \| `running` \| `complete` \| `aborted_by_user` \| `failed`                                                                                                                                                         |
| `Phase`          | integer or string    | yes      | Skill-defined phase identifier — numeric (`0`, `1`, `2.5`) or named (`research`, `red_verified`).                                                                                                                             |
| `PhaseName`      | string               | optional | Human-readable phase label when `Phase` is numeric.                                                                                                                                                                           |
| `Started`        | ISO-8601 timestamp   | yes      | When the task started — `2026-05-16T14:32:00Z` or `2026-05-16`.                                                                                                                                                               |
| `Iteration`      | integer              | optional | Iteration count for skills that loop. Default `0`; multiple counters use `<name>Iteration` keys.                                                                                                                              |
| `FilesWritten`   | YAML list of paths   | yes      | Cumulative artifact paths. Append-only; never truncate.                                                                                                                                                                       |
| `phase_complete` | boolean              | yes      | `false` on phase entry; `true` only once the phase's work is done **and** its post-conditions hold (artifacts written, gates passed). A resumer reads this to decide whether to re-run the recorded phase or advance past it. |
| `what_remains`   | YAML list of strings | yes      | Outstanding items for the current phase or task. May be `[]`. **MUST be `[]` when `Status: complete`.**                                                                                                                       |
| `last_verified`  | ISO-8601 timestamp   | optional | When the last verification gate (lint / test / review) passed. Tells a resumer how stale the green state is.                                                                                                                  |

Skill-specific keys (`Reproduced`, `Root cause`, `current_wave`, `criteria checklist`, …) are allowed and encouraged below the required block. Adding them does **not** bump the schema version — the version bumps only when the **required** key set changes.

## Progress-ledger discipline

`phase_complete`, `what_remains`, and `last_verified` are the **progress ledger** — the fields that tell a resumer *what is left*, not just *where it stopped*.

- **`phase_complete`** — set `false` the moment a phase is entered; set `true` only when that phase's work is genuinely done: every artifact it promises is on disk and every gate it owns has passed. A resumer that finds `true` advances to the next phase; one that finds `false` re-enters the recorded phase at its idempotent entry point.
- **`what_remains`** — refresh on every phase transition. List concrete outstanding items as plain strings a human can act on. It MUST be `[]` when `Status: complete` — a complete task with leftover items is a contradiction, and a resumer treats that file as `failed`.
- **`last_verified`** — stamp it whenever a verification gate passes clean. Leave it absent until the first gate passes.

## Minimal example

```yaml
schema_version: 2
Status: running
Phase: 6
PhaseName: implementation
Started: 2026-05-16T14:32:00Z
Iteration: 2
FilesWritten:
  - research.md
  - plan.md
  - tests/test_foo.py
phase_complete: false
what_remains:
  - wire the retry path into the request handler
  - add the timeout regression test
last_verified: 2026-05-16T15:10:00Z
# Skill-specific keys below this line:
current_wave: 2
work_units_remaining: 3
```

## Migration table

Migration is **read-time, forward-only, and purely additive** — no data loss, no field renames.

| From version | To version | Migration                                                                                                                                                                        |
| ------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (none)       | 2          | Legacy pre-schema file. Add `schema_version: 2`, `phase_complete: false`, `what_remains: []` (leave `last_verified` absent). Log `Upgraded legacy state file to schema v2.`      |
| 1            | 2          | Set `schema_version: 2`. Add `phase_complete: false` and `what_remains: []`; leave `last_verified` absent. Every v1 key is preserved unchanged. Log `Upgraded state file v1→v2.` |
| 2            | 2          | No-op (same version).                                                                                                                                                            |

A v2-aware skill performs the upgrade on read, before acting on the file, and never silently coerces a version it cannot migrate (see Mismatch policy).

## Mismatch policy

When a skill reads a `state.md` whose `schema_version` it does not recognize:

1. **Higher version than the skill knows** (file says `3`, skill knows `2`) — do NOT silently coerce. Treat as `BLOCKED` and escalate via AskUserQuestion: `restart` (abandon the file, start fresh — user confirms the overwrite) or `abort` (stop, touch nothing).
1. **Lower version than the skill knows** (file says `1`, skill knows `2`) — auto-migrate using the migration-table row. The `1 → 2` row always exists, so a v1 file never blocks.
1. **No `schema_version` field** (legacy pre-schema file) — apply the `(none) → 2` row, add the keys, and proceed.

## Compact inline contract

Plugins without a `shared/` schema file embed the block below in each skill's `SKILL.md` State Management section. It is a **delta contract** — it adds `schema_version` and the progress-ledger fields on top of whatever `Status` / `Phase` / `Started` keys the skill already writes. It does not retrofit keys such as `FilesWritten` that a skill does not already maintain; the table above is the complete schema, this block is the minimum a migrating skill must add.

> State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

## Why this exists

Without `schema_version`, any change to the state-file shape silently breaks resume: the reader guesses a parse and produces wrong behavior instead of detecting "I do not understand this file." Without the progress ledger, `state.md` records *where* a task stopped but not *what is left* — a resumer has to re-derive the outstanding work by hand, and context compaction has usually destroyed it. The ledger makes the file answer "re-run or advance?" directly.
