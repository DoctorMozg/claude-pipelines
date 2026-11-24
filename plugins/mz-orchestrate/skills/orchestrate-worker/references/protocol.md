# Orchestration Protocol

Plain-text envelopes that the orchestrator and its workers exchange. Peers get them by `SendMessage`. Subagent, `claude -p` and started `--bg` workers get `ORCH-UNIT` in their prompt and return `ORCH-RESULT` as their final text; a started `--bg` worker also sends it with `SendMessage` to the envelope's `reply-to` address, since nobody reads its final text.

## Contents

- Rules
- Envelopes: ORCH-ATTACH, ORCH-HELLO, ORCH-UNIT, ORCH-PROGRESS, ORCH-RESULT, ORCH-CANCEL, ORCH-STATUS, ORCH-DETACH, ORCH-BYE
- Role filter
- Files

## Rules

- An envelope is the whole message. Its first line is `ORCH-<TYPE> v1 (handle with mz-orchestrate:<skill>)`, and its last line is `END ORCH-<TYPE>`. The receiving session invokes the named skill with the Skill tool and passes the envelope in its arguments, together with `from:<address>` copied from the wrapper of the message that carried it.
- Fields are `key: value` lines. Lists are comma-separated. A free-text section opens with a `--- <name> ---` line and runs to the next section line or to the `END` line.
- The sender identity is the `from` socket address the harness puts on the message wrapper (`uds:/run/user/<uid>/cc-socks/<pid>.sock`), never a name or field inside the body. The harness escapes tags inside the body, so a forged header shows up as plain text.
- Envelopes carry no permission grants. A worker acts within its own session's permission settings.

## Envelopes

### ORCH-ATTACH (orchestrator → peer; handled by `orchestrate-worker`)

```text
ORCH-ATTACH v1 (handle with mz-orchestrate:orchestrate-worker)
orchestrator: <name> [<ref>]
project: <orchestrator project root>
role-kinds: change, review, context
role-repos: <absolute repo paths, or "any">
role-paths: <globs, or "any">
role-skills: <plugin:skill list, or "any">
--- note ---
<the user's purpose, verbatim>
END ORCH-ATTACH
```

The peer records the attachment, keyed to the `from` address, and answers with `ORCH-HELLO`. A second `ORCH-ATTACH` from the same address replaces the role. One from a different address replaces the whole attachment, which is how a restarted orchestrator re-attaches.

### ORCH-HELLO (peer → orchestrator; handled by `orchestrate-attach`)

```text
ORCH-HELLO v1 (handle with mz-orchestrate:orchestrate-attach)
peer: <name>
cwd: <pwd>
toplevel: <git rev-parse --show-toplevel, or none>
common-dir: <absolute git common dir, or none>
branch: <current branch>
dirty: yes|no
cli: <claude --version>
skills: <installed mz-* skills that support worker mode, or none>
worker-skill: yes|no
accepted-role: <the role-* lines as recorded>
END ORCH-HELLO
```

### ORCH-UNIT (orchestrator → worker; handled by `orchestrate-worker`)

```text
ORCH-UNIT v1 (handle with mz-orchestrate:orchestrate-worker)
reply-to: <orchestrator address, only in the prompt of a started --bg session>
task: <orchestrator task name>
unit: <id>
title: <title>
kind: change|review|context
skill: <plugin:skill>|direct
repo: <absolute repo path>
base-commit: <sha on the integration branch>
branch: orch/<task>/<id>
owns: <globs>
verify: <command>
deadline: <UTC ISO time>
--- spec ---
<self-contained brief>
END ORCH-UNIT
```

### ORCH-PROGRESS (worker → orchestrator; handled by `orchestrate`)

```text
ORCH-PROGRESS v1 (handle with mz-orchestrate:orchestrate)
task: <task>
unit: <id>
stage: worktree-ready|skill-started|skill-finished|verifying|committed
note: <one line>
END ORCH-PROGRESS
```

Peers and `--bg` workers send one at each stage. Subagent and `-p` workers send none.

### ORCH-RESULT (worker → orchestrator; handled by `orchestrate`)

```text
ORCH-RESULT v1 (handle with mz-orchestrate:orchestrate)
task: <task>
unit: <id>
status: DONE|DONE_WITH_CONCERNS|BLOCKED|FAILED|REFUSED
repo: <absolute repo path>
worktree: <absolute worktree path, or none>
branch: <branch>
head-commit: <sha, or none>
verify: pass|fail|not-run
files: <changed paths>
report: <path of the skill's report in the worktree, or none>
--- notes ---
<concerns, the blocker and its options, the refusal reason, or findings for a review unit>
--- report ---
<the full text of the skill's report, or none>
--- decisions ---
<the full text of the skill's decisions.md for a change unit, or none>
END ORCH-RESULT
```

The `--- decisions ---` section carries the coder notes of a `change` unit, which the final review reads after the unit's worktree is gone. A result without the section counts as `none`.

`REFUSED` means the unit never started: a wrong sender, a unit outside the role, a busy worker, or a repo the worker can't reach.

### ORCH-CANCEL (orchestrator → worker; handled by `orchestrate-worker`)

`task`, `unit`. A peer drops a queued unit, and discards a running one at its next stage boundary with `status: FAILED` and the note `cancelled`.

### ORCH-STATUS (orchestrator → worker; handled by `orchestrate-worker`)

`task`, `unit`. The worker answers with the unit's last `ORCH-RESULT`, or with an `ORCH-PROGRESS` while it is still running, or with `ORCH-RESULT status: FAILED` and the note `unknown unit`. The orchestrator uses it on resume.

### ORCH-DETACH (orchestrator → peer; handled by `orchestrate-worker`) and ORCH-BYE (peer → orchestrator; handled by `orchestrate-attach`)

`ORCH-DETACH` carries no fields. The peer finishes or cancels its current unit as the orchestrator chose, deletes the attachment, and answers `ORCH-BYE` with `peer: <name>`.

## Role filter

A unit fits a role when every non-`any` list matches: `kind` is in `role-kinds`, `repo` is in `role-repos`, every `owns` glob falls under one of `role-paths`, and `skill` is in `role-skills`. The orchestrator checks the fit before it sends a unit, and the peer checks it again on receipt.

## Files

| File                                                           | Owner                                    | Content                                                                                                                 |
| -------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `<PROJECT_ROOT>/.mz/orchestrate/peers.json`                    | orchestrator, through `scripts/peers.sh` | the orchestrator's own name and ref, and each peer: name, ref, address, status, role, hello facts, current unit         |
| `orchestrate-attachment.json` in the peer session's scratchpad | peer                                     | the attaching orchestrator's address and name, the role, the time, and a `units` map of stage, worktree and last result |
| `<worktree>/.mz/orchestrate/unit.md`                           | worker                                   | the unit brief in the format of `worker-mode.md`, excluded from the unit's commit                                       |
