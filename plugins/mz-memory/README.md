# mz-memory

Cross-session project memory for [Claude Code](https://claude.com/claude-code). Automatically persists knowledge across sessions, re-injects after compaction, and captures completed task summaries.

## Install

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-memory
```

Memory activates automatically on install — no configuration needed.

## How It Works

### Hook Lifecycle

| Hook                | Event        | What it does                                                  |
| ------------------- | ------------ | ------------------------------------------------------------- |
| **Memory inject**   | SessionStart | Reads `.mz/memory/MEMORY.md` and injects into context         |
| **Memory capture**  | SessionEnd   | Scans completed tasks, appends summaries, prunes to 200 lines |
| **Memory reinject** | PostCompact  | Re-injects memory after context compaction                    |

### Storage

Memory is stored at `.mz/memory/MEMORY.md` in the project root. It is:

- Human-readable and editable
- Git-trackable (add to `.gitignore` if you prefer per-developer memory)
- Capped at 200 lines to stay within context budget
- Most recent entries first (prepend strategy)

### What Gets Captured

- Completed task names and dates (from `.mz/task/*/state.md`)
- Manually added entries (edit the file directly)

### Memory Injection

At session start, the first 200 lines of `MEMORY.md` are injected as `additionalContext` (capped at 8000 chars). After context compaction, memory is re-injected to prevent knowledge loss.

## Pair With

- **mz-dev-pipe**: Pipeline agents (planner, coder) have `memory: project` for agent-specific persistent memory
- **mz-dev-hooks**: Safety gates work alongside memory hooks without conflict

## Per-Agent Native Memory

`mz-dev-pipe` agents declare `memory: project` in their agent frontmatter. Claude Code honors this declaration by giving each agent a project-scoped `MEMORY.md` at `.claude/agent-memory/<agent-name>/MEMORY.md`. Each persona (planner, coder, reviewer, etc.) gets its own independent memory file that persists across sessions.

This is **orthogonal** to the global memory system this plugin provides:

- **Global memory** (`mz-memory`) lives at `.mz/memory/MEMORY.md` and is shared across every session and every agent. It is the place for project-wide facts, decisions, and completed task summaries.
- **Per-agent memory** (`memory: project` frontmatter) lives at `.claude/agent-memory/<agent-name>/MEMORY.md` and is scoped to a single persona. It is the place for persona-specific conventions, lessons, and preferred patterns — things the coder needs to remember that the planner does not.

There is no overlap and no conflict. Both layers may coexist, and pipelines that use `mz-dev-pipe` will populate both: the global store through the session hooks in this plugin, and the per-agent stores through Claude Code's native memory handling.

## File Reference

| File                                        | Purpose                                              |
| ------------------------------------------- | ---------------------------------------------------- |
| `.mz/memory/MEMORY.md`                      | Project memory store (auto-created on first session) |
| `.claude/agent-memory/pipeline-*/MEMORY.md` | Per-agent native memory (managed by Claude Code)     |
