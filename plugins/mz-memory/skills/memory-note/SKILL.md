---
name: memory-note
description: ALWAYS invoke when the user wants to manually save a note, decision, or convention into project memory. Triggers "remember that", "note this", "save to memory", "pin this decision", "add to memory". Pins go to the persistent Pinned section; activity entries go to the rolling Activity Log.
argument-hint: <note body>  [--log to append to Activity Log instead of Pinned]
allowed-tools: Bash, Read, AskUserQuestion
model: haiku
---

# Memory Note

## Overview

Appends a single dated entry to `.mz/memory/MEMORY.md`. By default the entry goes to the **Pinned** section (persistent, never auto-pruned). Pass `--log` to append to the **Activity Log** instead (FIFO, capped at 200 lines).

## When to Use

- User says "remember that X", "note this", "pin the decision to use Y", "save to memory"
- User reports a convention, invariant, or decision that should outlive the current session
- User wants to leave a breadcrumb for the next session

### When NOT to use

- User wants to capture a completed task — that flows automatically through the SessionEnd hook
- User wants to read or search memory — they should open `.mz/memory/MEMORY.md` directly
- User wants to remove an entry — edit the file by hand

## Input

`$ARGUMENTS` — the note body. Inline modifiers:

- `--log` — append to Activity Log instead of Pinned (use for transient activity-style notes)

If `$ARGUMENTS` is empty, ask via `AskUserQuestion`. Never guess.

## Constants

- **MEMORY_FILE**: `.mz/memory/MEMORY.md`
- **NOTE_SCRIPT**: `${CLAUDE_PLUGIN_ROOT}/scripts/memory-note.sh`
- **MAX_BODY_CHARS**: 500 (longer notes get rejected — split or summarize)

## Core Process

### Phase 0: Parse

1. Strip `--log` if present; remember it as `target=log`, otherwise `target=pinned`.
1. Trim whitespace from the remaining body.
1. If body is empty → `AskUserQuestion` for the note text. Never guess.
1. If body length > MAX_BODY_CHARS → ask user to shorten or split. Never silently truncate.

### Phase 1: Confirmation Gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Pre-read**: Compute the exact entry that will be written (`- [YYYY-MM-DD] <body>`) and capture it into context.

**Surface 1 — emit the plan message.** Output the entry verbatim as a normal markdown chat message. Emit the full verbatim contents — do not substitute a path, summary, or placeholder. Structure:

```
## Memory note ready for review — memory-note

- [YYYY-MM-DD] <body>

Target section: <pinned|log>
File: .mz/memory/MEMORY.md

---
**Approve** → write the entry to MEMORY.md  ·  **Reject** → discard, no file changes  ·  reply with feedback to revise
```

**Surface 2 — call AskUserQuestion.** After the plan message, call AskUserQuestion. The question must NOT re-embed the entry — it lives in the plan message above.

- question: `The memory note above is ready for review.`
- options:
  - **Approve** — write the entry to MEMORY.md
  - **Reject** — discard, no file changes

**Response handling**:

- **Approve** → run `Bash NOTE_SCRIPT [--log] "<body>"`, then proceed to verification.
- **Reject** → stop. Do not write. Surface "Note discarded."
- **Any other reply (feedback)** → revise the body using the user's input, return to Surface 1, re-emit the full updated plan message from scratch with the new entry, re-present the selector. This is a loop — repeat until the user explicitly approves.

### Phase 2: Verification

After the script runs, output a visible final block:

```
Memory note written.
File:    .mz/memory/MEMORY.md
Section: <pinned|log>
Entry:   <verbatim entry line>
```

If the script exited non-zero, surface the stderr message and stop.

## Common Rationalizations

| Rationalization                | Rebuttal                                                        |
| ------------------------------ | --------------------------------------------------------------- |
| "skip the gate, just write it" | a wrong note pollutes pinned memory across every future session |
| "truncate the body silently"   | the user will not notice the loss until the lost detail matters |
| "default to Activity Log"      | log entries roll off; user-driven notes belong in Pinned        |

## Red Flags

- You wrote to `MEMORY.md` directly with Edit/Write instead of the helper script.
- You skipped the approval gate.
- You silently truncated a too-long body.
- You guessed the note body when `$ARGUMENTS` was empty.

## Error Handling

- Empty body → `AskUserQuestion` for the text. Never guess.
- Body > MAX_BODY_CHARS → ask user to shorten; do not truncate.
- `memory-note.sh` exits 2 → surface stderr and stop.
- `memory-note.sh` reports duplicate → surface the message; do not retry.

## State Management

This skill is single-shot — no `.mz/task/` state file is created. The only durable artifact is the line appended to `MEMORY.md`.
