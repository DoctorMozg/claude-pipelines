# State File Schema

Rules for `.mz/task/<task_name>/state.md`, the checkpoint a multi-phase skill writes so it can find its place again after compaction or an interruption. The schema is at version 2.

Claims about Claude Code behavior carry the short source tags described at the top of AGENTS_GUIDELINES.md: a doc page, a changelog version, an issue, or "observed" for behavior seen in a probe. Pages live under `code.claude.com/docs/en/`, and page tags without a version were checked against v2.1.316 on 2026-11-02. Facts about this repository cite the file they come from. A rule marked "Repo convention", or a rule with no tag, is this repository's own choice.

**Where the file lives.** `state.md` sits in `.mz/task/<task_name>/` under the project root defined in JOURNAL_GUIDELINES.md, "Project Root", not under the Bash working directory. Resume checks compute the task name from today's date, so a skill resumes only a task started the same day (`plugins/mz-base/shared/resume-protocol.md`).

**Runtime copies.** This file is for authors. Claude Code doesn't copy files outside a plugin's directory when it installs the plugin, so no skill can read `guidelines/` at runtime (plugins/loading.md). Two copies carry the schema into plugins:

- `plugins/mz-base/shared/state-schema.md` is the runtime mirror of the full schema. It reaches each consumer plugin through that plugin's `shared` link, and mz-dev-pipe skills read it as `<PLUGIN_ROOT>/shared/state-schema.md` (SKILL_GUIDELINES.md, "Phase and Reference Files").
- Skills in other plugins embed the compact contract (§9) in their State Management section.

When this file changes, update the mirror in the same release, and check `plugins/mz-base/shared/resume-protocol.md` and every inline copy against this file. Nothing checks them automatically.

**Owned elsewhere.**

- Task naming, and which skills keep state: SKILL_GUIDELINES.md, "State Management".
- The project root: JOURNAL_GUIDELINES.md, "Project Root".
- What a skill writes before and after an approval gate: SKILL_GUIDELINES.md, "Approval Gates".
- Escalating when nobody can answer: SKILL_GUIDELINES.md, "Error Handling and Escalation".
- The resume gate and its Resume, Restart and New options: `plugins/mz-base/shared/resume-protocol.md`.
- The journal, and the memory log that body sections feed: JOURNAL_GUIDELINES.md.

## 1. Key Block

The file opens with a block of plain `key: value` lines. Markdown body sections follow it (§4).

| Key              | Type                       | Required                                   | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | -------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema_version` | integer                    | yes                                        | Schema major version, currently `2`. Line 1 of the file. A skill sets it when it creates the file, and only a migration (§7) changes it.                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `Status`         | enum                       | yes                                        | Line 2 of the file. One of the values in §2, lowercase and unquoted.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `Phase`          | integer or string          | yes                                        | Skill-defined phase: numeric (`0`, `1`, `2.5`) or named (`research`, `2_atomized`). Use only letters, digits, `_`, `.` and `-`, because mz-memory logs the value only up to the first other character. Milestones go here, not in `Status`.                                                                                                                                                                                                                                                                                                                   |
| `PhaseName`      | string                     | optional                                   | Readable label for a numeric `Phase`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `Started`        | ISO-8601 date or timestamp | yes                                        | When the task started: `2026-05-16T14:32:00Z` or `2026-05-16`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `Iteration`      | integer                    | optional                                   | Iteration count for a skill that loops. Default `0`. Several counters use `<name>Iteration` keys.                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `FilesWritten`   | YAML list of paths         | when read back                             | Artifacts the task produced, appended as they are written. Paths are relative to the project root, such as `.mz/task/<task_name>/plan.md` rather than `plan.md`, and absolute for files outside it, such as notes in a vault. For bulk output, list the directory with a count: `.mz/task/<task_name>/proposals/ (39 files)`. Required in a skill that reads it back: every skill that follows `plugins/mz-base/shared/resume-protocol.md`, since its Resume step reloads the list, and `govern`, which checks the list before finishing. Optional elsewhere. |
| `phase_complete` | boolean                    | yes, except in single-dispatch skills (§3) | Whether the recorded phase is finished (§3).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `what_remains`   | YAML list of strings       | yes, except in single-dispatch skills (§3) | Outstanding items for the current phase or task. `[]` when `Status` is `complete`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `last_verified`  | ISO-8601 timestamp         | optional                                   | When the last verification gate (lint, test or review) passed clean. It tells a resumer how stale the green state is.                                                                                                                                                                                                                                                                                                                                                                                                                                         |

Format rules:

- Because `schema_version` is line 1, the key block has no `---` frontmatter fence.
- `Status` goes on line 2, and the other schema keys follow before any skill-specific key. mz-memory takes the first `Status:` and the first `Phase:` it finds anywhere in the file, even inside a longer key such as `AggregateStatus:`, so an earlier match would be read as the task's status (`plugins/mz-memory/scripts/memory-capture.sh`).
- The first write of the file includes `schema_version`, `Status`, `Phase`, `Started` and the ledger keys (§3). Later writes keep `schema_version` as it is.
- Skill-specific keys (`Reproduced`, `Root cause`, `current_wave`, …) go below the schema keys. They add to the schema and never rename or replace one of its keys.

**Versioning.** The version changes only for a change that an existing reader or an existing file can't absorb: a new required key, a renamed key, a changed type, or a removed `Status` value. Adding an optional key, a skill-specific key, or a `Status` value whose readers are updated in the same release doesn't change it. Making `FilesWritten` optional kept the schema at v2 because no reader breaks: the compact contract never required the key, and every skill that reads it back still writes it.

## 2. Status Values

`Status` holds one of six values, written lowercase and unquoted.

| Value             | Meaning                                                                                               | What a resume check does                        |
| ----------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `pending`         | The file exists and no phase has started yet.                                                         | Offers the resume gate.                         |
| `running`         | A phase is in progress, or a gate is waiting for an answer in an interactive session.                 | Offers the resume gate.                         |
| `blocked`         | The run stopped for an answer that can't come or an obstacle it can't clear. `what_remains` names it. | Offers the resume gate.                         |
| `complete`        | Every phase finished, and `what_remains` is `[]`.                                                     | Treats the task as finished and starts a `_vN`. |
| `aborted_by_user` | The user rejected a gate or cancelled the run.                                                        | Treats the task as finished and starts a `_vN`. |
| `failed`          | The run stopped on an error it couldn't recover from.                                                 | Offers the resume gate.                         |

- **Gates.** While a gate waits in an interactive session, `Status` stays `running` and `what_remains` holds `awaiting approval: <gate>`. `Status` becomes `blocked` only when no answer can come (SKILL_GUIDELINES.md, "Approval Gates").
- **Resume gate, unattended.** The resume gate is a variant gate, so an unattended run doesn't pick Resume, Restart or New (SKILL_GUIDELINES.md, "Approval Gates"). It reports the path, `Status` and `what_remains` and stops, leaving the file untouched because it still describes the earlier run.
- **Blockers.** For `blocked`, `what_remains` names the blocker and the options, for example `awaiting approval: plan gate` or `awaiting answer: widen scope to global, or stop`.
- **Milestones**, such as `proposals_ready` or `scan_complete`, go in `Phase`.
- **Reasons** go in `what_remains` or a skill-specific key, never in a suffix on `Status`. A run that gets no usable CV path after two prompts writes `Status: blocked` with `what_remains: [awaiting answer: path to the CV file]`, not `Status: aborted_missing_cv`.
- **Nothing to do.** A run that ends early because there is nothing to do is `complete`, with the reason in `Phase`, such as `Phase: empty_scope`.
- **Why lowercase and unquoted.** mz-memory reads only lowercase letters and underscores after `Status: `, so `"complete"` and `Complete` are never logged (`plugins/mz-memory/scripts/memory-capture.sh`).
- **Legacy `completed`.** Readers treat `completed`, which older skills wrote, as `complete`. Writers use `complete`.

## 3. Progress Ledger

`phase_complete`, `what_remains` and `last_verified` tell a resumer what is left, not only where the task stopped.

- **`phase_complete`**: set it to `false` when a phase starts, and to `true` once every artifact the phase promises is on disk and every gate it owns has passed. A resumer that finds `true` advances to the next phase. One that finds `false` re-enters the recorded phase at its idempotent entry point (`plugins/mz-base/shared/resume-protocol.md`).
- **`what_remains`**: refresh it on every phase transition. List concrete outstanding items as plain strings a person can act on. It is `[]` when `Status` is `complete`, because a complete task with leftover items contradicts itself.
- **`last_verified`**: stamp it whenever a verification gate passes clean. Leave it out until the first one passes.

**Single-dispatch skills.** A skill that runs setup, one dispatch and its report in a single turn, with no approval gate and no phase files, may leave out `phase_complete` and `what_remains`. It still writes `Status`, `Phase` and `Started`. When it upgrades an older file, it adds only `schema_version: 2`. Its State Management section uses the second block in §9.

## 4. Body Sections

Below the key block, `state.md` is markdown. Four level-2 sections have a fixed meaning:

- `## Decisions`: one line per decision worth remembering across sessions, most important first, such as an approved artifact and where it landed, or an approach chosen over another and why. SKILL_GUIDELINES.md, "Approval Gates", asks for an entry here after a substantial gate decision.
- `## Lessons`: one line per thing a later run should do differently.
- `## Notes`: other short facts worth keeping.
- `## Auto-approvals`: one line per gate skipped in unattended mode, with the gate label, the phase and the time (the unattended-mode paragraph of SKILL_GUIDELINES.md, "Approval Gates"). mz-memory doesn't harvest it; the final report lists its entries.

Other sections, such as an error log, are free-form. Keep them short (§6).

**What mz-memory harvests.** When mz-memory is installed, its SessionEnd hook reads each `state.md` changed since its last run, or the 50 most recently changed ones on its first run (`plugins/mz-memory/scripts/memory-capture.sh`):

1. It takes the first `Status:` value and continues only for `complete` or the legacy `completed`.
1. It logs the task name, the first `Phase:` value, and the branch and commit.
1. It copies the first 10 non-blank lines of `## Decisions`, `## Lessons` and `## Notes`, counted together in file order, into the Activity Log of `.mz/memory/MEMORY.md`.

Write for it this way:

- Write each heading exactly: level two, the same case, nothing after the word. `## Decisions (2026-11-02)`, `## decisions` and `### Decisions` are skipped.
- Put `## Decisions` first of the three. A long `## Notes` above it uses up the 10 lines before any decision is read.
- A `##` heading ends a section. A `###` line doesn't, and it counts toward the 10.
- `<private>…</private>` spans are removed after the 10 lines are chosen, so a private line still takes one of them.
- Editing a finished `state.md` logs the task again at the next SessionEnd.
- A task that never reaches `complete` is never harvested, so a decision from a `failed`, `blocked` or `aborted_by_user` task doesn't reach the memory log. If it matters, pin it with `/memory-note`; the journal isn't read for recall.
- One changed `state.md` without a plain `Status:` line, or a `complete` one without a `Phase:` line, stops the capture, and every later capture fails until that file is fixed. Forms that stop it include `**Status:** running`, `status: running`, `Status:running` and a file with no `Status` key; the same goes for `Phase` in a `complete` file. `**Status**: running` happens to match, but don't rely on it; write the plain form from §1.

The Activity Log's format and size cap are in JOURNAL_GUIDELINES.md.

## 5. Minimal Example

A task in its implementation phase. `current_wave` and `work_units_remaining` are skill-specific keys.

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

## 6. Compaction

`state.md` survives compaction because it is on disk, but its content is back in context only once it is read again. A compaction summary keeps the user's requests and key code snippets, and detailed instructions from early in the conversation may be lost (how-claude-code-works.md).

**When to write.** Write `state.md` after every phase transition and just before every approval gate. Compaction has several triggers, and one of them can fire while a gate waits:

- Auto-compaction runs when the context reaches the auto-compact window. By default that is the model's context limit, with exceptions such as about 967K tokens on models with a native 1M window and 200K for Sonnet 4.6 and Opus 4.6 without extended context (model-config.md, "Default auto-compact thresholds"). `autoCompactWindow` changes the window, and agent frontmatter accepts it too (settings-reference.md; changelog 2.1.296).
- Idle compaction compacts an interactive conversation whose context has reached 200,000 tokens after about an hour idle, when the conversation is on the one-hour prompt cache. That cache is the default on a Claude subscription within plan usage (settings-reference.md, `idleCompaction`; prompt-caching.md; changelog 2.1.299, 2.1.314). It doesn't apply to subagents.
- Subagents auto-compact as their own context fills (sub-agents.md).

**What comes back.** After compaction, Claude Code re-reads up to five of the files Claude read or edited, most recently modified first, and a file over 5,000 tokens comes back only as a path. Invoked skill bodies come back capped at 5,000 tokens each and 25,000 in total, keeping the start of each (context-window.md). The docs describe these re-reads for the main conversation and don't say whether a compacting subagent gets them. `state.md` is usually the most recently modified file, so it is among the five, and its content comes back as long as it stays under 5,000 tokens.

**Rules.**

- Keep `state.md` well under 5,000 tokens, roughly 20,000 characters. Record bulk output as a directory with a count (§1), put long logs in their own files in the task directory, and keep body sections to one line per entry.
- After compaction, re-read `state.md` explicitly before acting, then the current phase file (SKILL_GUIDELINES.md, "Phase and Reference Files"). Don't rely on the automatic re-read or on the summary.
- Put the resume check and a resume pointer near the top of SKILL.md, where truncation won't reach them. The pointer is one line naming the `state.md` path and saying to re-read it after compaction.
- Read cross-phase facts, such as paths, decisions and counters, back from `state.md`, not from conversation memory.

## 7. Migration

A skill migrates the file when it reads it, before acting on it. Migration runs forward only and adds keys without renaming or dropping any.

| From   | To  | Migration                                                                                                                                                                                                                                                                                                |
| ------ | --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (none) | 2   | Legacy file without a version. Add `schema_version: 2` as line 1, removing a `---` fence if the file has one, and move the `Status` line to line 2 if it isn't there. Then add `phase_complete: false` and `what_remains: []`. Leave `last_verified` out. Log `Upgraded legacy state file to schema v2.` |
| 1      | 2   | Change `schema_version` to `2`, move the `Status` line to line 2 if it isn't there, and add `phase_complete: false` and `what_remains: []`. Leave `last_verified` out. Every v1 key stays as it was. Log `Upgraded state file v1→v2.`                                                                    |
| 2      | 2   | Nothing to do.                                                                                                                                                                                                                                                                                           |

Migration leaves the `Status` value as it is, and readers treat a legacy `completed` as `complete` (§2). A single-dispatch skill adds only `schema_version: 2` (§3). A skill never coerces a version it can't migrate (§8).

## 8. Mismatch Policy

When a skill reads a `state.md` whose `schema_version` it doesn't know:

1. **Higher than the skill knows** (the file says `3`, the skill knows `2`). Don't modify the file. Two Claude Code installs with different plugin versions can share one `.mz/task/`, so the file may belong to a newer skill.
   - In an interactive main session, ask with AskUserQuestion, offering three options. **Restart** renames the task directory to `<task_name>_archived_<YYYY_MM_DD_HHMMSS>` and starts fresh. **New** leaves the directory untouched and starts `<task_name>_v2`, or the next free `_vN`. **Abort** stops without touching anything. New is the safer choice when another install may still be using the directory.
   - Where nobody can answer, stop and report the path and both versions. A skill running in a subagent returns `STATUS: BLOCKED`. Unattended mode doesn't pick an option either; it takes this path. This is the one blocker that isn't written to `state.md`, because a skill can't safely write a file it doesn't understand. The general rule is in SKILL_GUIDELINES.md, "Error Handling and Escalation".
1. **Lower than the skill knows** (the file says `1`). Migrate with the matching row in §7. The `1 → 2` row always exists, so a v1 file never blocks.
1. **No `schema_version`.** Apply the `(none) → 2` row and continue.

## 9. Compact Inline Contract

Skills that don't read the runtime copy embed one of these blocks in their State Management section. §1 is the full schema; the block names what every skill writes, and a skill adds its own keys below the schema keys as needed. Both blocks spell out the root expression from JOURNAL_GUIDELINES.md, "Project Root", because a plugin can't read `guidelines/`; when that section changes, update the blocks.

Multi-phase skills:

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase`, `Started`, `phase_complete` (boolean) and `what_remains` (YAML list of strings), with skill-specific keys below them. Milestones go in `Phase`; the reason for `blocked` or `failed` goes in `what_remains`. Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass. Refresh `what_remains` on every phase transition; it is `[]` when `Status` is `complete`. Write the file after every phase and before every gate, and re-read it after compaction. Record decisions worth recalling under a heading that reads exactly `## Decisions`, placed before `## Lessons` and `## Notes`; mz-memory harvests them only once `Status` is `complete`. Treat a legacy `completed` as `complete`. On reading a `schema_version: 1` or unversioned file, put `schema_version: 2` on line 1 and `Status` on line 2, add the missing keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

Single-dispatch skills (§3):

> State persists to `.mz/task/<task_name>/state.md` under the project root, `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`, resolved once at the start of the run. Schema is **v2**: line 1 is `schema_version: 2`; line 2 is `Status:` with one of `pending`, `running`, `blocked`, `complete`, `aborted_by_user` or `failed`, lowercase and unquoted; then `Phase` and `Started`. This skill runs setup, one dispatch and its report in a single turn with no approval gate, so it leaves out `phase_complete` and `what_remains`. On reading an older file, put `schema_version: 2` on line 1 and `Status` on line 2, add no other keys, and log the upgrade. Leave a file with a higher `schema_version` untouched: ask whether to Restart (archive it), start New (`_v2`) or Abort, and stop if nobody can answer.

## 10. Why This Exists

Without `schema_version`, a change to the file's shape breaks resume silently: the reader guesses at a parse and does the wrong thing instead of noticing that it doesn't understand the file. Without the progress ledger, `state.md` records where a task stopped but not what is left, so a resumer has to re-derive the outstanding work, and the compaction summary may no longer hold it. The ledger answers "re-run or advance?" directly, and the fixed status values let a resume check and mz-memory tell a finished task from one that stopped.
