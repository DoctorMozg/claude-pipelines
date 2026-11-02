---
name: memory-note
description: 'Saves a note or decision to project memory. Use when the user wants something remembered ("remember that", "note this", "save to memory", "pin this decision"). Not for lookups (open MEMORY.md).'
argument-hint: '<the note, verbatim as the user wrote it>  [--log to append to Activity Log instead of Pinned]'
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/memory-note.sh *), Bash(date *), Read, AskUserQuestion
---

# Memory Note

## Overview

Appends a single dated entry to `.mz/memory/MEMORY.md`. By default the entry goes to the **Pinned** section (persistent, never auto-pruned). Pass `--log` to append to the **Activity Log** instead (FIFO, capped at 400 lines).

## When to Use

Records one note, decision, convention or invariant the user wants to outlive the current session, as a dated entry in `.mz/memory/MEMORY.md`.

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
- **MAX_BODY_CHARS**: 500 (longer notes go back to the user to shorten or split; never shorten them yourself)

## Core Process

### Phase 0: Parse

1. Strip `--log` if present; remember it as `target=log`, otherwise `target=pinned`.
1. Trim whitespace from the remaining body.
1. If body is empty → `AskUserQuestion` for the note text. Never guess.
1. Count the characters of the note as the user wrote it in their message, not the Skill arguments, which may already be condensed. If it is longer than MAX_BODY_CHARS, ask the user to shorten or split it. Never shorten it yourself.

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
- header: `Memory note`
- options:
  - **Approve** — write the entry to MEMORY.md
  - **Reject** — discard, no file changes

**Response handling**:

- **Approve** → run `Bash NOTE_SCRIPT [--log] "<body>"`, then proceed to verification.
- **Reject** → stop. Do not write. Surface "Note discarded."
- **Any other reply (feedback)** → revise the body using the user's input, return to Surface 1, re-emit the full updated plan message from scratch with the new entry, re-present the selector. This is a loop — repeat until the user explicitly approves.
- **No answer** → stop. A missing answer is never approval.

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
| "shorten the note to fit"      | the user will not notice the loss until the lost detail matters |
| "default to Activity Log"      | log entries roll off; user-driven notes belong in Pinned        |

## Red Flags

- You wrote to `MEMORY.md` directly with Edit/Write instead of the helper script.
- You skipped the approval gate.
- You truncated or condensed a too-long note instead of handing it back to the user.
- You guessed the note body when `$ARGUMENTS` was empty.

## Error Handling

- Empty body → `AskUserQuestion` for the text. Never guess.
- The user's note > MAX_BODY_CHARS → ask the user to shorten or split it; do not truncate or condense it yourself.
- `memory-note.sh` exits 2 → surface stderr and stop.
- `memory-note.sh` reports duplicate → surface the message; do not retry.

## State Management

This skill is single-shot — no `.mz/task/` state file is created. The only durable artifact is the line appended to `MEMORY.md`.
