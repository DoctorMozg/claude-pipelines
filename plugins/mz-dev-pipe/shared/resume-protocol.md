# Resume Protocol

Canonical source: this file owns the resume gate; the statuses it reads come from STATE_SCHEMA.md, "Status Values" (repository guidelines, not shipped with the plugin).

How a skill uses an existing `state.md` when it starts. `state-schema.md` defines the keys and statuses, and `approval-gate.md` defines the gate pattern this gate follows.

## On entry

Run this in setup, before creating the task directory:

1. Compute the candidate task name, `<YYYY_MM_DD>_<skill>_<slug>`, from today's date. A skill therefore resumes only a task started the same day.
1. Look for `<PROJECT_ROOT>/.mz/task/<task_name>/state.md`.
1. Branch on what you find:
   - **No file**: a fresh task. Create the directory and write `state.md` with `schema_version: 2`, `Status` (`pending` until the first phase starts, then `running`), `Phase`, `Started`, `phase_complete: false` and `what_remains: []`. Add `FilesWritten: []` when the skill reads it back.
   - **A higher `schema_version` than the skill knows**: follow the mismatch policy in `state-schema.md` before anything below.
   - **`Status: complete`, `completed` or `aborted_by_user`**: a finished task. Start `<task_name>_v2`, or the next free `_vN`, as a fresh task, and say so in chat.
   - **`Status: pending`, `running`, `blocked` or `failed`**: an unfinished task. Migrate an older file first (`state-schema.md`, "Migration"), then present the resume gate.
   - **Any other `Status` value**, such as a milestone an older skill wrote there: treat the task as unfinished and present the resume gate, quoting the value.

## Resume gate

A variant gate with four actions, following `approval-gate.md`. It writes nothing before it is answered, because the file still describes the earlier run.

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Read `<PROJECT_ROOT>/.mz/task/<task_name>/state.md` in full.

**Surface 1: emit the plan message.**

```text
## Existing task found: <skill name>

Task `<task_name>` stopped at Phase <Phase> (<PhaseName>) with Status: <status>. The phase is <finished or unfinished> (`phase_complete: <bool>`). Outstanding: <what_remains items, or "none">.

<verbatim state.md contents>

---
**Resume** → continue from the recorded phase  ·  **Restart** → archive the old task and start fresh  ·  **New** → keep the old task and start `<task_name>_v2`  ·  **Abort** → stop and change nothing
```

**Surface 2: call AskUserQuestion.** question: "A task with this name already exists. How should I proceed?" header: "Resume"
options:

- **Resume** — continue from the recorded phase with the existing artifacts
- **Restart** — archive the old task directory and start fresh
- **New** — keep the old task untouched and start a `_v2`
- **Abort** — stop without changing anything

## Response handling

- **Resume**: read back `Phase`, `phase_complete`, `what_remains`, any `Iteration` counters, `FilesWritten` and the skill's own keys. If `phase_complete` is `true`, go to the next phase's entry point. If it's `false`, re-enter the recorded phase at its idempotent entry point. If the file has no `FilesWritten`, rebuild the list from the task directory's contents and say so in chat. Set `Status: running` and drop any `awaiting …` entry before continuing; a gate that was waiting is presented again from Surface 1.
- **Restart**: rename `<PROJECT_ROOT>/.mz/task/<task_name>/` to `<task_name>_archived_<YYYY_MM_DD_HHMMSS>/`, create a fresh directory, continue as a fresh task, and give the archive path in chat.
- **New**: leave the directory untouched, take the next free `_vN` name, and continue as a fresh task.
- **Abort**: stop without touching any file.
- **Any other answer**: answer the question or adjust as asked, then present the gate again.
- **No answer, or unattended mode**: the resume gate never picks an action by itself. Report the path, `Status` and `what_remains`, then stop. Leave the file untouched, because it still describes the earlier run.

## Phase idempotency

A skill can be resumed only if every phase can run again without corrupting earlier output. Each phase file states its re-entry rule:

1. **Append-only writes.** A phase that builds output incrementally, such as `FilesWritten` or multi-wave coder output, appends from the recorded position instead of truncating.
1. **Idempotent file writes.** A phase that writes one artifact, such as `research.md` or `plan.md`, may overwrite it on re-entry. Its phase file says so.
1. **External side effects.** A phase that sends network requests, posts to GitHub or changes anything outside the repository records each side effect in `state.md` before making it, and skips the recorded ones on re-entry.
1. **Counters.** A phase with an iteration counter reads it back from `state.md` on re-entry instead of resetting it to zero.

A phase that can't meet these rules is marked non-resumable in its phase file. When the recorded phase is non-resumable, the resume gate offers only Restart, New and Abort.
