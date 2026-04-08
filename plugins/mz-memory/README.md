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

## File Reference

| File                                        | Purpose                                              |
| ------------------------------------------- | ---------------------------------------------------- |
| `.mz/memory/MEMORY.md`                      | Project memory store (auto-created on first session) |
| `.claude/agent-memory/pipeline-*/MEMORY.md` | Per-agent native memory (managed by Claude Code)     |
