# Mozg Session Handoff (`mz-handoff`)

Session handoff for [Claude Code](https://claude.com/claude-code). Each compaction summarizes the previous summary, so a long session drifts. After a few compactions, mz-handoff has Claude write down where the work stands, built from the transcript and git rather than from what the context still remembers. Then you type `/clear`, and the fresh session picks the file up. One skill ships with it: `/mz-handoff:handoff`.

## Install

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-handoff
```

## How it works

| Hook                | Event                                | What it does                                                                                            |
| ------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Handoff session** | SessionStart (startup/clear/compact) | Flags each compaction, loads this terminal's handoff after `/clear`, and lists open handoffs on startup |
| **Handoff stop**    | Stop                                 | After `MZ_HANDOFF_AFTER` compactions (default 3), keeps Claude going once to write a handoff            |

The flow:

1. The hooks count `compact_boundary` lines in the main transcript. Subagent compactions don't count, and the count starts over after `/clear`.
1. At `MZ_HANDOFF_AFTER` compactions the Stop hook blocks the stop once, and Claude runs `/mz-handoff:handoff`. Each later compaction gets a one-line reminder instead.
1. The skill writes `.mz/handoff/<YYYY_MM_DD_HHMM>_<first 8 chars of session id>.md` from facts that `handoff-facts.sh` reads out of the transcript and git. Where the facts and the model's memory of the session disagree, the facts win.
1. Claude asks you to type `/clear`. Nothing can clear a session for you.
1. After `/clear`, SessionStart picks the handoff whose `claude_pid` matches the same `claude` process, so parallel terminals stay apart. It injects a short pointer of at most 2000 characters (goal, first next steps, commit), not the whole file. With no match it lists up to three open handoffs. A fresh start also lists them and loads none on its own.
1. `/mz-handoff:handoff resume` reads the whole file, checks `git log <head>..HEAD`, reads the user messages sent after the handoff, runs the "Verify on resume" commands, then marks the file `status: claimed <session id>` so no later session loads it again.

You can also run `/mz-handoff:handoff` by hand at any time.

### What a handoff contains

A handoff has YAML frontmatter (session, `claude_pid`, transcript, branch, head, `status`) and these sections, in at most 150 lines:

- **Goal** and the criterion for done
- **Constraints**, quoted verbatim from your messages with their time
- **Decisions**
- **Done**, each item with evidence: a commit, a path, or a command and its result
- **Assumed not verified**
- **Tried and failed**
- **Next**, one to three steps
- **Open questions**
- **Files touched**
- **Verify on resume**, the commands that prove the current state

For a running pipeline, the handoff points at the task's `.mz/task/<task_name>/state.md` and doesn't copy it.

## Configuration

| Variable           | Meaning                                                                                                                     |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `MZ_HANDOFF_AFTER` | Compactions before the handoff nudge (default 3). `0` turns off the automatic nudge only. Manual runs and pickup still work |
| `MZ_MEMORY_ROOT`   | Override project-root detection (absolute path)                                                                             |

The project root is the nearest `.git` above `CLAUDE_PROJECT_DIR`, the same `.mz/` root mz-memory uses. A `MZ_HANDOFF_AFTER` value that isn't a whole number logs a warning and falls back to 3. Set it in the `env` block of `settings.json`:

```json
{ "env": { "MZ_HANDOFF_AFTER": "5" } }
```

## Files

| Path                            | Role                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `.mz/handoff/*.md`              | Handoff files, newest first when listed                                                                 |
| `.mz/handoff/.due/`, `.nudged/` | Per-session markers: a compaction to count, and the count last reported. Pruned after 7 days at startup |
| `scripts/handoff-session.sh`    | SessionStart hook: flags compactions, loads or lists handoffs                                           |
| `scripts/handoff-stop.sh`       | Stop hook: counts compactions, blocks once, then reminds                                                |
| `scripts/handoff-facts.sh`      | Prints the session ids, git state, written files and your messages the skill builds from                |
| `scripts/lib/handoff.sh`        | Helpers: threshold, compaction count, `claude` process lookup, frontmatter, root                        |
| `scripts/awk/*.awk`             | The awk programs the hooks run                                                                          |
| `skills/handoff/SKILL.md`       | Write mode and resume mode                                                                              |

## Requirements

bash and `jq`. Without `jq` the hooks exit silently, and `handoff-facts.sh` exits 1 with a message. `ps` is used to find the `claude` process.

## Limits

- The first skill call may ask for a permission.
- Codex transcripts have no `compact_boundary` line, so the nudge stays inert there.
- The process-ID pickup is unit-tested but not yet exercised in a live interactive session.

## Data and network

Everything stays on the machine, and the plugin makes no network calls.

- **Reads:** the session transcript under `~/.claude/projects/` (or `CLAUDE_CONFIG_DIR`), git, and `ps`.
- **Writes:** `.mz/handoff/` only.
- The skill writes secrets and `<private>` text as `[redacted]`.

## License

MIT
