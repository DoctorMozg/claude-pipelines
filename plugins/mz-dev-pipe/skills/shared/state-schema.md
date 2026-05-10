# State File Schema — v1

Canonical schema for `.mz/task/<task_name>/state.md` across every mz-dev-pipe skill. The state file is the single load-bearing checkpoint that survives context compaction. Every skill MUST write it, every skill MUST be able to read it, and every skill MUST refuse to operate on a state file whose `schema_version` it does not recognize.

## Required keys (schema v1)

Every `state.md` written by a mz-dev-pipe skill MUST contain at minimum these top-level keys:

| Key              | Type               | Purpose                                                                                                              |
| ---------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | integer            | Schema major version. Currently `1`. Skills refuse to operate on unrecognized versions.                              |
| `Status`         | enum               | `pending` \| `running` \| `complete` \| `aborted_by_user` \| `failed`                                                |
| `Phase`          | integer or string  | Skill-defined phase identifier. Numeric (`0`, `1`, `2.5`) or named (`research`, `planning`, `red_verified`).         |
| `PhaseName`      | string (optional)  | Human-readable phase label when `Phase` is numeric (e.g., `Phase: 6`, `PhaseName: implementation`).                  |
| `Started`        | ISO-8601 timestamp | When the task started. Format: `2026-05-10T14:32:00Z` or `2026-05-10`.                                               |
| `Iteration`      | integer (optional) | Current iteration count for skills that loop. Default `0`. Skills with multiple counters use `<name>Iteration` keys. |
| `FilesWritten`   | YAML list of paths | Cumulative list of artifact paths produced by the skill so far. Append-only; never truncate.                         |

Skill-specific keys (e.g., `Reproduced`, `Root cause`, `current_wave`, `criteria checklist`) are allowed and encouraged. They live below the required block. Skills may add any additional keys they need without bumping the schema version — the schema bumps only when the **required** key set changes.

## Minimal example

```yaml
schema_version: 1
Status: running
Phase: 6
PhaseName: implementation
Started: 2026-05-10T14:32:00Z
Iteration: 2
FilesWritten:
  - research.md
  - plan.md
  - tests/test_foo.py
# Skill-specific below this line:
current_wave: 2
work_units_remaining: 3
```

## Migration table

| From version | To version | Migration                                                                                                                      |
| ------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1            | 1          | No-op (same version).                                                                                                          |
| (none)       | 1          | Pre-schema-versioned files. Add `schema_version: 1` to the top and proceed. Skills SHOULD warn the user the file was upgraded. |

When the schema bumps to v2 in the future, this table grows to describe the v1→v2 transformation. New rows MUST include the exact field renames, type changes, and default values for any new required fields.

## Mismatch policy

When a skill reads a `state.md` whose `schema_version` it does not recognize:

1. **Higher version than the skill knows about** (e.g., file says `schema_version: 2`, skill code knows only `1`):
   - Skill MUST NOT silently coerce. Treat as `BLOCKED`.
   - Escalate via AskUserQuestion with options:
     - `migrate` — only valid if the skill has a forward-migration path; usually not.
     - `restart` — abandon the file, start a new task. User confirms file overwrite.
     - `abort` — stop without touching the file.
1. **Lower version than the skill knows about** (e.g., file says `schema_version: 1`, skill code knows `2`):
   - Skill MAY auto-migrate using the migration table if the row exists.
   - If no migration row exists, escalate as above.
1. **No `schema_version` field at all** (legacy pre-schema file):
   - Treat as the implicit `(none) → 1` migration row. Add `schema_version: 1` and proceed. Log a one-line warning: `Upgraded legacy state file to schema v1.`

## Schema-version writers

Every skill that writes `state.md` for the first time during a task MUST include `schema_version: 1` on the first line of the file. No exceptions. Subsequent updates to the same file (appending to `FilesWritten`, advancing `Phase`, etc.) MUST preserve the field unchanged.

## Why this exists

Without `schema_version`, any future change to the state-file shape silently breaks resume. The plugin promises resumability via `state.md` (see `shared/resume-protocol.md`). That promise is only enforceable if the reader can detect "I do not understand this file" instead of guessing a parse and producing wrong behavior.

This is a 1.0 ship-blocker: any state-file change after 1.0 must follow the migration discipline above.
