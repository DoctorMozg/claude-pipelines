---
name: orchestrate-detach
description: 'Detaches worker sessions from this orchestrator so they stop taking units. Use when the user says "detach an agent" or "release a session". Not for changing a purpose (use orchestrate-attach).'
argument-hint: '[<session name> ...] [all]'
allowed-tools: SendMessage, AskUserQuestion, Read, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/peers.sh *), Bash(git rev-parse *)
---

# Orchestrate Detach

## Overview

Releases sessions that `/orchestrate-attach` made into workers. The user picks them from the registry; each gets `ORCH-DETACH`, deletes its attachment and answers `ORCH-BYE`. A session that is running a unit gets a choice first: wait for the unit, give it to another worker, or cancel it.

## When to Use

- The user wants an attached session back for its own work, or wants to stop orchestration from reaching it.
- A session was attached by mistake or with the wrong purpose and should be released rather than re-purposed.

### When NOT to use

- Changing a session's purpose: `/orchestrate-attach <name> "<new purpose>"` keeps it attached.
- Stopping a whole orchestration run: answer **Abort** at the orchestrator's out-of-plan gate.

## Input

- No arguments: show the attached sessions and ask.
- `<session name> ...`: detach those. `all`: detach every attached and pending session.

## Constants

- **PROJECT_ROOT**: `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`.
- **REGISTRY**: `<PROJECT_ROOT>/.mz/orchestrate/peers.json`, written only through `${CLAUDE_PLUGIN_ROOT}/scripts/peers.sh REGISTRY <command>`.
- **PROTOCOL**: `${CLAUDE_PLUGIN_ROOT}/skills/orchestrate-worker/references/protocol.md`.

## Core Process

### Step 1: Pick the sessions

Run `peers.sh REGISTRY list`. No registry or no `attached`/`pending` peers: say nothing is attached and stop.

- Names in the arguments: match them against the list, and report names that aren't there.
- No names: show the peers as a chat table (name, status, purpose, current unit). Then call AskUserQuestion with `multiSelect: true`, up to 4 peers per question and up to 4 questions per call; each option's label is the name, and its description is the purpose and current unit.

### Step 2: Settle running units

For each chosen peer whose `current_unit` is set, ask one variant question, header `Unit`:

- **Wait**: detach after the unit's `ORCH-RESULT` arrives and is merged.
- **Reassign**: cancel it here, and let `/orchestrate` send the unit to another worker.
- **Cancel**: cancel it, and mark the unit for the out-of-plan gate.

**Wait** sets `peers.sh REGISTRY status <name> detaching` and stops for that peer: `/orchestrate` sends `ORCH-DETACH` when the result is in. **Reassign** and **Cancel** send `ORCH-CANCEL` for the unit and record the choice in the orchestrator's task `state.md` under `## Notes`, so `/orchestrate` acts on it at its next step.

### Step 3: Send ORCH-DETACH

For each peer ready to go: SendMessage `ORCH-DETACH` to `<name> [<ref>]`, then `peers.sh REGISTRY status <name> detaching`. The peer's `ORCH-BYE` brings `/orchestrate-attach bye`, which marks it `detached`. A peer that is gone from ListAgents, or a send that fails, is removed with `peers.sh REGISTRY remove <name>` and reported.

Show a summary table: session, what happened to its unit, and the new status.

## Error Handling

- AskUserQuestion denied or unanswered: detach only the names given in the arguments. A running unit with no answer is treated as **Wait**, which loses nothing.
- `peers.sh` exits non-zero: show its stderr and stop.

## State Management

This skill keeps no `.mz/task/` state. It changes the registry through `peers.sh`, and for **Reassign** or **Cancel** it adds one line to the running orchestration's `state.md`.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/orchestrate-worker/references/protocol.md`: `ORCH-DETACH`, `ORCH-BYE`, `ORCH-CANCEL` and the registry fields.
