---
name: orchestrate-attach
description: 'Attaches other running Claude sessions as orchestration workers, each with a purpose limiting its units. Use when the user says "attach agents" or "use my other session for the UI", or an ORCH-HELLO arrives. Not for removal (use orchestrate-detach).'
argument-hint: '[<session name> ["<purpose>"] ...] | hello | bye'
allowed-tools: ListAgents, SendMessage, AskUserQuestion, Read, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/peers.sh *), Bash(git rev-parse *)
---

# Orchestrate Attach

## Overview

Turns running Claude sessions on this machine into workers for `/orchestrate`. The user picks sessions from the live list and gives each a purpose in plain words, such as "only UI in the web repo" or "only for review". The purpose becomes a role filter: the orchestrator sends that session only units that fit it, and the session refuses anything else. Attached sessions run units with no confirmation, inside their own permission settings.

Attaching is asynchronous. This skill sends `ORCH-ATTACH` and records each peer as `pending`; each peer answers later with `ORCH-HELLO`, which arrives as a new message and brings this skill back with `hello` to mark the peer `attached`.

## When to Use

- The user wants other sessions to take work from this one, now or before running `/orchestrate`.
- The user wants to change what an attached session is for: run this skill again with the same name and a new purpose.
- An `ORCH-HELLO` or `ORCH-BYE` message arrives that names `mz-orchestrate:orchestrate-attach`.

### When NOT to use

- Removing a worker: `/orchestrate-detach`.
- Running a plan: `/orchestrate`, which uses whatever is attached.
- Messaging a session once, without making it a worker: use SendMessage directly.

## Input

- No arguments: show the list of sessions and ask.
- `<session name> ["<purpose>"]`, repeated: attach those sessions directly. A name without a purpose gets the purpose question.
- `hello <envelope> from:<address>` or `bye <envelope> from:<address>`: record a peer's answer.

## Constants

- **PROJECT_ROOT**: `${MZ_MEMORY_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}`.
- **REGISTRY**: `<PROJECT_ROOT>/.mz/orchestrate/peers.json`, written only through `${CLAUDE_PLUGIN_ROOT}/scripts/peers.sh REGISTRY <command>`.
- **PROTOCOL**: `${CLAUDE_PLUGIN_ROOT}/skills/orchestrate-worker/references/protocol.md`. Read it before building the first envelope.
- **PEERS_PER_QUESTION**: 4 and **QUESTIONS_PER_CALL**: 4, the AskUserQuestion limits, so one call shows at most 16 sessions.

## Core Process

### Step 1: Know who this session is

Call ListAgents and follow its cursor to the last page. The header line names this session, `<name> [<ref>]`. Run `peers.sh REGISTRY init <name> <ref>`. That creates the registry if needed and records a new ref after a restart.

### Step 2: Pick the sessions

Candidates are the listed sessions minus this one and minus peers already `attached` or `pending` (`peers.sh REGISTRY list`), unless the user named one of those to change its purpose.

- Names in the arguments: match each against the listing. A name that isn't listed is reported, and the rest go on.
- No names: show the candidates as a chat table (name, kind, busy or idle, age). Then call AskUserQuestion with `multiSelect: true`, up to 4 sessions per question and up to 4 questions per call. Each option's label is the session name, and its description is `<kind> · <busy|idle> · started <age>`. More than 16 candidates: say so in the table and let the user type further names in `Other`.
- No candidates: say that no other session is running or reachable, mention that `--bg` sessions and sessions on other machines need Remote Control to show up, and stop.

### Step 3: Give each one a purpose

Every chosen session without a purpose from the arguments gets one question, header `Purpose`, with three options:

- **Any unit**: it can take any unit the orchestrator assigns.
- **Review only**: it only gets review units and the final branch review.
- **Only its own repo**: it only gets units in the repository it is working in.

`Other` takes free text, such as "only UI in the web repo". Ask about four sessions per call.

Turn each purpose into a role (PROTOCOL, "Role filter"): `kinds`, `repos`, `paths`, `skills`, each a list or `"any"`, plus `note`, the user's words verbatim.

- **Any unit**: everything `"any"`.
- **Review only**: `kinds: ["review"]`.
- **Only its own repo**: `repos: ["own"]`, resolved from the peer's `ORCH-HELLO`.
- Free text: map what it names to the closest fields; paths become globs (`web/**`). Keep anything that doesn't map in `note` only. The orchestrator's compiler reads the note when it routes units.

### Step 4: Send ORCH-ATTACH

For each session: `peers.sh REGISTRY add <name> <ref> '<role json>'` (or `role` when it is already attached), then SendMessage to `<name> [<ref>]` with an `ORCH-ATTACH` envelope from PROTOCOL. `role-repos: own` stays literal in the envelope; the peer resolves it to its own repository.

Show a summary table: session, purpose as typed, the role it became, and status `pending`. Tell the user that answers arrive as messages, and that a session busy with its own work answers when its current turn ends. A misread purpose is fixed by running `/orchestrate-attach <name> "<new purpose>"`.

### Step 5: Record answers (`hello`, `bye`)

- **hello**: find the peer whose name matches the envelope's `peer` field and whose status is `pending` or `attached`. An envelope from a name that isn't in the registry gets a one-line note in chat and is otherwise ignored. Otherwise run `peers.sh REGISTRY hello <name> <from address> '<hello json>'`; the hello JSON holds every field of the envelope. A `repos: ["own"]` role becomes the peer's `toplevel` with `peers.sh REGISTRY role`. Report in one line: the peer, its repo and branch, its role, and whether it has the worker skill and the worker-mode skills. A peer without `orchestrate-worker` can't run units: say so and suggest installing mz-orchestrate there.
- **bye**: `peers.sh REGISTRY status <name> detached`, and report it in one line.

## Error Handling

- SendMessage fails for a session: mark it with `peers.sh REGISTRY status <name> refused`, report the error, and go on with the others.
- A delivery notice says the peer holds or refuses inbound messages: mark it `refused` and tell the user to set `crossSessionInbound` to `accept` in that session's settings, then attach again.
- `peers.sh` exits non-zero: show its stderr and stop. It never leaves a half-written registry.
- AskUserQuestion denied or unanswered: attach only the sessions named with a purpose in the arguments, and list the rest as not attached.

## State Management

This skill keeps no `.mz/task/` state. The registry at REGISTRY is its only artifact, and `peers.sh` writes it atomically.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/orchestrate-worker/references/protocol.md`: the envelopes, the role filter and the registry fields.
