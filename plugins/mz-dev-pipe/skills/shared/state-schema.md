# State File Schema — v2

Canonical schema for `.mz/task/<task_name>/state.md` across every mz-dev-pipe skill. The state file is the single load-bearing checkpoint that survives context compaction. Every skill MUST write it, every skill MUST be able to read it, and every skill MUST refuse to operate on a state file whose `schema_version` it does not recognize.

This file is the **mz-dev-pipe runtime copy** of the repo-level authoring canonical at `guidelines/STATE_SCHEMA.md`. mz-dev-pipe skills reference *this* file via the relative path `skills/shared/state-schema.md`; they do not read `guidelines/`, which does not ship inside an installed plugin. When the canonical changes, mirror the change here.

## Required keys (schema v2)

Every `state.md` written by a mz-dev-pipe skill MUST contain at minimum these top-level keys:

| Key              | Type                          | Purpose                                                                                                                                                                                                                       |
| ---------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | integer                       | Schema major version. Currently `2`. Skills refuse to operate on unrecognized versions.                                                                                                                                       |
| `Status`         | enum                          | `pending` \| `running` \| `complete` \| `aborted_by_user` \| `failed`                                                                                                                                                         |
| `Phase`          | integer or string             | Skill-defined phase identifier. Numeric (`0`, `1`, `2.5`) or named (`research`, `planning`, `red_verified`).                                                                                                                  |
| `PhaseName`      | string (optional)             | Human-readable phase label when `Phase` is numeric (e.g., `Phase: 6`, `PhaseName: implementation`).                                                                                                                           |
| `Started`        | ISO-8601 timestamp            | When the task started. Format: `2026-05-10T14:32:00Z` or `2026-05-10`.                                                                                                                                                        |
| `Iteration`      | integer (optional)            | Current iteration count for skills that loop. Default `0`. Skills with multiple counters use `<name>Iteration` keys.                                                                                                          |
| `FilesWritten`   | YAML list of paths            | Cumulative list of artifact paths produced by the skill so far. Append-only; never truncate.                                                                                                                                  |
| `phase_complete` | boolean                       | `false` on phase entry; `true` only once the phase's work is done **and** its post-conditions hold (artifacts written, gates passed). A resumer reads this to decide whether to re-run the recorded phase or advance past it. |
| `what_remains`   | YAML list of strings          | Outstanding items for the current phase or task. May be `[]`. **MUST be `[]` when `Status: complete`.**                                                                                                                       |
| `last_verified`  | ISO-8601 timestamp (optional) | When the last verification gate (lint/test/review) passed. Tells a resumer how stale the green state is.                                                                                                                      |

Skill-specific keys (e.g., `Reproduced`, `Root cause`, `current_wave`, `criteria checklist`) are allowed and encouraged. They live below the required block. Skills may add any additional keys they need without bumping the schema version — the schema bumps only when the **required** key set changes.

## Progress-ledger discipline

`phase_complete`, `what_remains`, and `last_verified` are the progress ledger — the fields that tell a resumer *what is left*, not just *where it stopped*.

- Set `phase_complete: false` on entering a phase; set it `true` only once that phase's artifacts are all written and its gates have passed. A resumer that finds `true` advances; one that finds `false` re-enters the phase at its idempotent entry point.
- Refresh `what_remains` on every phase transition. It MUST be `[]` when `Status: complete` — a complete task with leftover items is a contradiction.
- Stamp `last_verified` whenever a lint/test/review gate passes clean; leave it absent until the first gate passes.

## Minimal example

```yaml
schema_version: 2
Status: running
Phase: 6
PhaseName: implementation
Started: 2026-05-10T14:32:00Z
Iteration: 2
FilesWritten:
  - research.md
  - plan.md
  - tests/test_foo.py
phase_complete: false
what_remains:
  - wire the retry path into the request handler
  - add the timeout regression test
last_verified: 2026-05-10T15:10:00Z
# Skill-specific below this line:
current_wave: 2
work_units_remaining: 3
```

## Migration table

Migration is read-time, forward-only, and purely additive — no data loss, no field renames.

| From version | To version | Migration                                                                                                                                                                        |
| ------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (none)       | 2          | Pre-schema-versioned file. Add `schema_version: 2`, `phase_complete: false`, `what_remains: []` (leave `last_verified` absent). Log `Upgraded legacy state file to schema v2.`   |
| 1            | 2          | Set `schema_version: 2`. Add `phase_complete: false` and `what_remains: []`; leave `last_verified` absent. Every v1 key is preserved unchanged. Log `Upgraded state file v1→v2.` |
| 2            | 2          | No-op (same version).                                                                                                                                                            |

The `1 → 2` row is purely additive: a skill reading a `schema_version: 1` file adds the three ledger keys and proceeds. No prior key changes type or name.

**Legacy Status tokens**: files written before enum enforcement may carry `Status: completed` or `Status: in_progress`. On read, normalize them to `complete` / `running`, rewrite the file, and log the normalization. These are token spellings, not schema versions — normalizing them does not bump `schema_version`.

## Mismatch policy

When a skill reads a `state.md` whose `schema_version` it does not recognize:

1. **Higher version than the skill knows about** (e.g., file says `schema_version: 3`, skill code knows only `2`):
   - Skill MUST NOT silently coerce. Treat as `BLOCKED`.
   - Escalate via AskUserQuestion with options:
     - `restart` — abandon the file, start a new task. User confirms file overwrite.
     - `abort` — stop without touching the file.
1. **Lower version than the skill knows about** (e.g., file says `schema_version: 1`, skill code knows `2`):
   - Skill auto-migrates using the migration-table row. The `1 → 2` row always exists, so a v1 file never blocks.
1. **No `schema_version` field at all** (legacy pre-schema file):
   - Treat as the `(none) → 2` migration row. Add the keys and proceed. Log `Upgraded legacy state file to schema v2.`

## Schema-version writers

Every skill that writes `state.md` for the first time during a task MUST include `schema_version: 2` on the first line of the file, and MUST write `phase_complete` and `what_remains` in that same initial write. No exceptions. Subsequent updates to the same file (appending to `FilesWritten`, advancing `Phase`, flipping `phase_complete`, refreshing `what_remains`) MUST preserve `schema_version` unchanged.

## Why this exists

Without `schema_version`, any future change to the state-file shape silently breaks resume. The plugin promises resumability via `state.md` (see `shared/resume-protocol.md`). That promise is only enforceable if the reader can detect "I do not understand this file" instead of guessing a parse and producing wrong behavior.

The progress ledger (`phase_complete`, `what_remains`) extends that promise: a resumer learns not just which phase it stopped in but whether that phase finished and what work is still outstanding — the context that compaction destroys first.

Any state-file change must follow the migration discipline above.
