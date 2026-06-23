# mz-memory

Cross-session project memory for [Claude Code](https://claude.com/claude-code). Automatically persists knowledge across sessions, re-injects after compaction, captures pre-compaction handover state, selectively injects relevant memory on each prompt, and ships a `/memory-note` skill for manual pinning.

## Install

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-memory
```

Memory activates automatically on install — no configuration needed.

## How It Works

### Hook Lifecycle

| Hook                  | Event                         | What it does                                                                     |
| --------------------- | ----------------------------- | -------------------------------------------------------------------------------- |
| **Memory inject**     | SessionStart                  | Reads `.mz/memory/MEMORY.md` (Pinned + Activity Log) and injects into context    |
| **Memory capture**    | SessionEnd                    | Scans completed tasks, pulls Decisions/Lessons sections, attaches `[branch@sha]` |
| **Memory reinject**   | PostCompact                   | Re-injects memory after context compaction                                       |
| **Memory precompact** | PreCompact                    | Snapshots in-flight working state from the transcript before compaction          |
| **Memory prompt**     | UserPromptSubmit              | Selectively injects pinned + matching log entries based on prompt keywords       |
| **Journal capture**   | PostToolUse `AskUserQuestion` | Appends every approval gate and input prompt verbatim to `.mz/journal.md`        |

### Storage

Memory is stored at `.mz/memory/MEMORY.md` in the project root. The file uses a **two-region layout**:

```
## Pinned
<!-- mz-pinned-start -->
- [2026-05-05] always run migrations forward-compatible
<!-- mz-pinned-end -->

## Activity Log
<!-- mz-log-start -->
- [2026-05-05] task_name (phase=done) [branch@sha]
  - Decision lines pulled from state.md
<!-- mz-log-end -->
```

- **Pinned**: persistent invariants and decisions. Never auto-pruned. Edit by hand or use `/memory-note`.
- **Activity Log**: rolling FIFO, capped at 200 entries. Most recent first. Auto-populated by SessionEnd.

The file is human-readable, git-trackable (add to `.gitignore` for per-developer memory), and resilient to header corruption — the marker comments (`<!-- mz-pinned-start -->` etc.) anchor every insert, so the structure repairs itself if the header is hand-edited.

### Project Root Detection

`mz-memory` walks up from `CLAUDE_PROJECT_DIR` (or the current working directory) to the nearest `.git`, so a single `MEMORY.md` is shared across every subdirectory of a monorepo. Override with `MZ_MEMORY_ROOT=/abs/path` if needed.

### What Gets Captured Automatically

- Completed task names and dates (from `.mz/task/*/state.md` where `Status: completed`)
- Phase, current branch, and short SHA at session-end time
- The first 10 lines of any `## Decisions`, `## Lessons`, or `## Notes` section in the task's `state.md`
- Per-agent routing: if the state file mentions `[agent-name]` for any agent under `.claude/agent-memory/<agent-name>/`, the entry is also appended to that agent's `MEMORY.md`

### Privacy

Wrap sensitive substrings with `<private>...</private>` tags in your task state files or note bodies. The capture and `/memory-note` paths strip these regions before persisting; surrounding whitespace is collapsed.

### Selective Injection on UserPromptSubmit

Each prompt is tokenized (alphanumeric, length ≥ 4, common stopwords dropped, capped at 12 keywords). Pinned content is always included; Activity Log entries are filtered by keyword match (case-insensitive, max 15 matches, capped at 2000 chars). Empty result → silent (no payload).

This is the 10× token-savings pattern from progressive-disclosure memory architectures: don't dump 200 lines into every prompt — only inject what the user is currently asking about.

### PreCompact Handover

Before the harness compresses the transcript, `memory-precompact.sh` reads `transcript_path` from stdin, tails the last 200 lines, and emits them (plus the Pinned section) as additional context that gets appended to the compaction prompt. With `MZ_MEMORY_PRECOMPACT_LLM=1` and `claude` on PATH, a fresh `claude -p` instance summarizes the tail into 8–15 bullets instead.

### Optional LLM Compression

When `MZ_MEMORY_COMPRESS=1` is set and `claude` is on PATH, SessionEnd will detach a background `memory-compress.sh` process whenever the Activity Log exceeds 300 entries. It keeps the most recent 100 verbatim and replaces the rest with a themed summary (`## Recurring decisions`, `## Resolved bugs`, etc.). Failure is silent — compression is best-effort and never blocks the session.

## Interaction Journal

Alongside curated memory, `mz-memory` records a raw **interaction journal** at `.mz/journal.md` — one global, append-only, gitignored log of every approval gate, input prompt, and decision across all skills. Where `MEMORY.md` is the distilled recall store, the journal is the verbatim audit trail of how agents and the user actually negotiated each step.

A `PostToolUse` hook matched to `AskUserQuestion` captures every gate and input automatically — question and answer, verbatim — so the trail survives even when context is compacted and the model forgets it is mid-gate. Skills may append richer entries (skill, task, phase, the artifact under review) via `journal-append.sh`. `<private>…</private>` regions are redacted to `[redacted]` before writing, with code formatting preserved.

Decisions worth recalling are promoted from the journal into memory: write a `## Decisions` section into the task's `state.md` and the SessionEnd capture lifts it into the Activity Log, and thus into the next session's injected context. The journal itself is disposable scratch; the memory store is what persists.

The entry format, the two-layer (hook + skill) capture model, and the redaction convention are specified in [`guidelines/JOURNAL_GUIDELINES.md`](../../guidelines/JOURNAL_GUIDELINES.md).

## Manual Notes: `/memory-note`

```
/memory-note always run migrations forward-compatible
/memory-note --log ad-hoc activity entry
```

Adds a single dated line to **Pinned** by default, or to the **Activity Log** with `--log`. The skill goes through an approval gate before writing — no surprise edits to project memory.

## Environment Variables

| Variable                     | Effect                                                         |
| ---------------------------- | -------------------------------------------------------------- |
| `MZ_MEMORY_ROOT`             | Override project-root detection (absolute path)                |
| `MZ_MEMORY_COMPRESS=1`       | Enable background LLM compression of long Activity Logs        |
| `MZ_MEMORY_PRECOMPACT_LLM=1` | Use `claude -p` to summarize the transcript tail in PreCompact |

## Pair With

- **mz-dev-pipe**: Pipeline agents (planner, coder) have `memory: project` for agent-specific persistent memory; the per-agent bridge in `memory-capture.sh` automatically routes tagged task entries into their files

## Per-Agent Native Memory

`mz-dev-pipe` agents declare `memory: project` in their agent frontmatter. Claude Code honors this declaration by giving each agent a project-scoped `MEMORY.md` at `.claude/agent-memory/<agent-name>/MEMORY.md`. Each persona gets its own independent memory file that persists across sessions.

This is **complementary** to the global memory system this plugin provides:

- **Global memory** (`mz-memory`) lives at `.mz/memory/MEMORY.md` and is shared across every session and every agent. It is the place for project-wide facts, decisions, and completed task summaries.
- **Per-agent memory** (`memory: project` frontmatter) lives at `.claude/agent-memory/<agent-name>/MEMORY.md` and is scoped to a single persona.
- **Bridged**: when a task's `state.md` contains `[agent-name]` for any agent under `.claude/agent-memory/`, the SessionEnd capture writes the entry to both the global log AND that agent's file, closing the loop between the two layers.

## File Reference

| File                                          | Purpose                                                                      |
| --------------------------------------------- | ---------------------------------------------------------------------------- |
| `.mz/memory/MEMORY.md`                        | Project memory store with Pinned + Activity Log sections                     |
| `.mz/memory/.compress.lock`                   | Atomic lock held by background compression                                   |
| `.mz/journal.md`                              | Append-only interaction journal (gates, inputs, decisions) — gitignored      |
| `.claude/agent-memory/<agent>/MEMORY.md`      | Per-agent native memory (managed by Claude Code, bridged on capture)         |
| `scripts/lib/common.sh`                       | Shared helpers: `find_project_root`, `strip_private`, `atomic_write`, …      |
| `scripts/memory-{inject,capture,reinject}.sh` | Core SessionStart / SessionEnd / PostCompact hooks                           |
| `scripts/memory-precompact.sh`                | PreCompact handover-snapshot hook                                            |
| `scripts/memory-prompt-inject.sh`             | UserPromptSubmit selective-injection hook                                    |
| `scripts/memory-compress.sh`                  | Optional background LLM compaction of the Activity Log                       |
| `scripts/journal-capture.sh`                  | PostToolUse(AskUserQuestion) hook — records gates/inputs to `.mz/journal.md` |
| `scripts/journal-append.sh`                   | CLI helper — flock-guarded, `<private>`-redacting journal appender           |
| `scripts/memory-note.sh`                      | CLI helper invoked by the `/memory-note` skill                               |
| `skills/memory-note/SKILL.md`                 | Manual-note slash command with approval gate                                 |
