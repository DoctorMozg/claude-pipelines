# State File Schema (v2)

Canonical source: STATE_SCHEMA.md (repository guidelines, not shipped with the plugin).

Rules for `state.md`, the checkpoint a multi-phase skill writes so it can find its place again after compaction or an interruption. The file lives at `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`. The project root is `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run, not the Bash working directory.

## Contents

- Key block
- Status values
- Example
- Body sections
- Compaction
- Single-dispatch skills
- Migration
- Mismatch policy
- Compact inline contract

## Key block

The file opens with plain `key: value` lines, with no `---` fence, followed by markdown body sections.

| Key              | Required                              | Rule                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schema_version` | yes                                   | Line 1. Currently `2`. Set when the file is created; only a migration changes it.                                                                                                                                                                                                                                                                                                                                                                            |
| `Status`         | yes                                   | Line 2. One of the six values below, lowercase and unquoted.                                                                                                                                                                                                                                                                                                                                                                                                 |
| `Phase`          | yes                                   | Numeric (`0`, `2.5`) or named (`research`, `2_atomized`), using only letters, digits, `_`, `.` and `-`. Milestones go here.                                                                                                                                                                                                                                                                                                                                  |
| `PhaseName`      | optional                              | Readable label for a numeric `Phase`.                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `Started`        | yes                                   | `2026-05-16T14:32:00Z` or `2026-05-16`.                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `Iteration`      | optional                              | Loop counter, default `0`. Several counters use `<name>Iteration` keys.                                                                                                                                                                                                                                                                                                                                                                                      |
| `FilesWritten`   | when read back                        | Artifacts the task produced, appended as they're written. Paths are relative to the project root (`.mz/task/<task_name>/plan.md`, not `plan.md`), or absolute for files outside it. Record bulk output as a directory with a count: `.mz/task/<task_name>/proposals/ (39 files)`. Required in every skill that follows `resume-protocol.md`. When a file that needs it has none, as after a migration, Resume rebuilds it from the files in the task folder. |
| `phase_complete` | yes, except in single-dispatch skills | `false` when a phase starts; `true` once every artifact the phase promises is on disk and every gate it owns has passed.                                                                                                                                                                                                                                                                                                                                     |
| `what_remains`   | yes, except in single-dispatch skills | YAML list of outstanding items a person can act on, refreshed on every phase transition. `[]` when `Status` is `complete`.                                                                                                                                                                                                                                                                                                                                   |
| `last_verified`  | optional                              | When the last lint, test or review gate passed clean. Leave it out until the first one passes.                                                                                                                                                                                                                                                                                                                                                               |

- The first write includes `schema_version`, `Status`, `Phase`, `Started` and the ledger keys.
- Schema keys come first. Skill-specific keys (`Reproduced`, `current_wave`, …) go below them and don't rename or replace a schema key. mz-memory reads the first `Status:` and the first `Phase:` anywhere in the file, even inside a longer key such as `AggregateStatus:`, so an earlier match would be read as the task's status.
- Write the file after every phase transition and just before every approval gate.

## Status values

| Value             | Meaning                                                                                               | What a resume check does |
| ----------------- | ----------------------------------------------------------------------------------------------------- | ------------------------ |
| `pending`         | The file exists and no phase has started.                                                             | offers the resume gate   |
| `running`         | A phase is in progress, or a gate is waiting for an answer in an interactive session.                 | offers the resume gate   |
| `blocked`         | The run stopped for an answer that can't come or an obstacle it can't clear; `what_remains` names it. | offers the resume gate   |
| `complete`        | Every phase finished, and `what_remains` is `[]`.                                                     | starts a `_vN`           |
| `aborted_by_user` | The user rejected a gate or cancelled the run.                                                        | starts a `_vN`           |
| `failed`          | The run stopped on an error it couldn't recover from.                                                 | offers the resume gate   |

- While a gate waits, `Status` stays `running` and `what_remains` holds `awaiting approval: <gate>`. It becomes `blocked` only when no answer can come.
- For `blocked`, `what_remains` names the blocker and the options, such as `awaiting answer: widen scope to global, or stop`.
- Milestones such as `proposals_ready`, `scan_complete` and `plan_approved` go in `Phase`.
- Reasons go in `what_remains` or a skill-specific key, never as a suffix on `Status`. A run that gets no usable CV path writes `Status: blocked` with `what_remains: [awaiting answer: path to the CV file]`, not `Status: aborted_missing_cv`.
- A run that ends early because there's nothing to do is `complete`, with the reason in `Phase`, such as `Phase: empty_scope`.
- Readers treat a legacy `completed` as `complete`. Writers use `complete`.
- A `Status` that holds a milestone, a reason suffix or any other value outside this table counts as unfinished: the resume gate is offered, and the next write corrects the value.
- The resume gate is a variant gate. It never picks an action by itself, unattended or with no answer; `resume-protocol.md` has the rules.

## Example

```
schema_version: 2
Status: running
Phase: 6
PhaseName: implementation
Started: 2026-05-16T14:32:00Z
Iteration: 2
FilesWritten:
  - .mz/task/2026_05_16_build_retry_path/research.md
  - .mz/task/2026_05_16_build_retry_path/plan.md
  - tests/test_retry.py
phase_complete: false
what_remains:
  - wire the retry path into the request handler
  - add the timeout regression test
last_verified: 2026-05-16T15:10:00Z
current_wave: 2
work_units_remaining: 3

## Decisions
- plan approved: .mz/task/2026_05_16_build_retry_path/plan.md
- jittered backoff instead of a fixed delay, because the upstream API rate-limits bursts
```

## Body sections

- `## Decisions`: one line per decision worth remembering, most important first, such as an approved artifact and where it landed.
- `## Lessons`: one line per thing a later run should do differently. Write one whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, as `- (<trigger>) WHEN <situation> → <what to do> — WHY <cause>` with `<trigger>` one of `review`, `failure`, `correction` or `change`. Keep it concrete and under about 40 words, and record a review finding only once it was accepted and fixed.
- `## Notes`: other short facts worth keeping.
- `## Auto-approvals`: one line per gate skipped in unattended mode, with the gate label, the phase and the time. It isn't harvested; the final report lists it.

Other sections, such as `## Concerns` from `agent-status-protocol.md` or an error log, are free-form. Keep them short.

When mz-memory is installed, its SessionEnd hook reads each `state.md` changed since its last run, or the 50 most recently changed ones on its first run:

1. Whatever the `Status`, it copies up to 10 bullet lines of `## Lessons` into the Inbox of `.mz/memory/lessons.md`, tagged with the trigger, the task, the commit and the status.
1. It takes the first `Status:` value and goes on to the Activity Log only for `complete` or the legacy `completed`.
1. It logs the task name, the first `Phase:` value, and the branch and commit.
1. It copies the first 10 non-blank lines of `## Decisions` and `## Notes`, counted together in file order, into `.mz/memory/MEMORY.md`.

Write for it this way:

- Write each heading exactly: level two, the same case, nothing after the word. `## Decisions (2026-11-02)`, `## decisions` and `### Decisions` are skipped.
- Put `## Decisions` before `## Notes`, so a long `## Notes` doesn't use up the 10 lines.
- A `##` heading ends a section. A `###` line doesn't, and under `## Decisions` and `## Notes` it counts toward the 10. Under `## Lessons` only bullet lines (`-`, `*` or `1.`) are read.
- `<private>…</private>` spans are removed before anything is stored. Under `## Decisions` and `## Notes` that happens after the 10 lines are chosen, so a private line still uses one of them.
- Editing a finished `state.md` logs the task again at the next SessionEnd. A lesson already harvested from the same task is skipped, so an edit adds only the new lessons; the same lesson from another task is kept as a recurrence.
- Decisions and Notes from a task that never reaches `complete` are never logged. If a decision from a `failed`, `blocked` or `aborted_by_user` task matters, pin it with `/memory-note`. Its `## Lessons` are harvested all the same.
- A file without a plain `Status:` line is never logged, even when it finished: `**Status:** complete`, `status: complete`, `Status:complete` and a missing `Status` key all miss. Its lessons are still harvested, with `status=unknown`. A `complete` file without a `Phase:` line is logged without its phase. Neither stops the capture of other files.

## Compaction

- Keep `state.md` well under 5,000 tokens, roughly 20,000 characters, because a larger file comes back after compaction only as a path. Record bulk output as a directory with a count, put long logs in their own files in the task directory, and keep body sections to one line per entry.
- After compaction, re-read `state.md` before acting, then the current phase file. Don't rely on the summary.
- Keep the resume check and a one-line resume pointer near the top of SKILL.md. The pointer names the `state.md` path and says to re-read it after compaction.
- Read cross-phase facts, such as paths, decisions and counters, back from `state.md`, not from memory of the conversation.
- An interactive conversation over 200,000 tokens can compact after about an hour idle, and that can happen while a gate waits.

## Single-dispatch skills

A skill that runs setup, one dispatch and its report in a single turn, with no approval gate and no phase files, may leave out `phase_complete` and `what_remains`. It still writes `Status`, `Phase` and `Started`. When it upgrades an older file, it adds only `schema_version: 2`.

## Migration

Migrate when you read the file, before acting on it. Migration runs forward only. It adds keys without renaming or dropping any, and it leaves the `Status` value as it is.

| From   | To  | Migration                                                                                                                                                                                                                                              |
| ------ | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| (none) | 2   | Add `schema_version: 2` as line 1, removing a `---` fence if the file has one, and move the `Status` line to line 2. Add `phase_complete: false` and `what_remains: []`, and leave `last_verified` out. Log `Upgraded legacy state file to schema v2.` |
| 1      | 2   | Change `schema_version` to `2`, move the `Status` line to line 2, and add `phase_complete: false` and `what_remains: []`. Every v1 key stays as it was. Log `Upgraded state file v1→v2.`                                                               |
| 2      | 2   | Nothing to do.                                                                                                                                                                                                                                         |

A single-dispatch skill adds only `schema_version: 2`.

## Mismatch policy

A file whose `schema_version` is higher than the skill knows may belong to a newer install that shares the same `.mz/task/`. Don't modify it.

- In an interactive main session, ask with AskUserQuestion and offer three options:
  - **Restart**: rename the task directory to `<task_name>_archived_<YYYY_MM_DD_HHMMSS>` and start fresh.
  - **New**: leave the directory untouched and start `<task_name>_v2`, or the next free `_vN`. New is the safer choice when another install may still be using the directory.
  - **Abort**: stop without touching anything.
- Where nobody can answer, unattended mode included, stop and report the path and both versions. A skill running in a subagent returns `STATUS: BLOCKED`. This is the one blocker that isn't written to `state.md`, because the skill can't safely write a file it doesn't understand.

A lower version, or a missing `schema_version`, migrates by the table above and never blocks.

## Compact inline contract

Skills that don't read this file put one of these blocks, verbatim, in their State Management section.

Multi-phase skills:

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase`, `Started`, `phase_complete` (boolean) and `what_remains` (YAML list of strings), with skill-specific keys below them. Milestones go in `Phase`; the reason for `blocked` or `failed` goes in `what_remains`. Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass. Refresh `what_remains` on every phase transition; it is `[]` when `Status` is `complete`. Write the file after every phase and before every gate, and re-read it after compaction. Record decisions worth recalling under a heading that reads exactly `## Decisions`, placed before `## Notes`; mz-memory harvests them only once `Status` is `complete`. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed, a step fails, gate feedback corrects a mistake, or an approved approach is reversed, in the form `- (review|failure|correction|change) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`. Treat a legacy `completed` as `complete`. On reading a `schema_version: 1` or unversioned file, put `schema_version: 2` on line 1 and `Status` on line 2, add the missing keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

Single-dispatch skills:

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase` and `Started`. This skill runs setup, one dispatch and its report in a single turn with no approval gate, so it leaves out `phase_complete` and `what_remains`. Under a heading that reads exactly `## Lessons`, add one line whenever a review finding is accepted and fixed or a step fails, in the form `- (review|failure) WHEN <situation> → <what to do> — WHY <cause>`, concrete and under about 40 words; mz-memory harvests lessons whatever the `Status`. On reading an older file, put `schema_version: 2` on line 1 and `Status` on line 2, add no other keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.
