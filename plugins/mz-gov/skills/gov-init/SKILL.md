---
name: gov-init
description: ALWAYS invoke when the user wants to install or update the governance policy in CLAUDE.md. Triggers:"gov init","install governance policy","set up governance". NOT for running a decision (use govern) or auditing artifacts (use gov-review).
argument-hint: '[project|global] [--force] [--uninstall]'
model: sonnet
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Gov Init

## Overview

Install the `mz-gov` governance policy into `CLAUDE.md` so Claude proactively reaches for the `govern` pipeline on substantial, ambiguous decisions. The policy is injected as a single sentinel-wrapped block — idempotent on re-run, cleanly removable on `--uninstall`. This is the only delivery mode: the block goes into `CLAUDE.md`, nothing else.

## When to Use

Triggers: "gov init", "install governance policy", "set up governance", "add govern policy to CLAUDE.md".

### When NOT to use

- The user wants to run a governance decision on a change — use `govern`.
- The user wants to audit existing artifacts — use `gov-review`.
- The user wants to edit the policy text itself — open the injected block in `CLAUDE.md` directly, or re-run with `--force` after editing the source.
- `CLAUDE.md` is managed by another tool and must not be touched.

## Arguments

- `project` (default) → inject into `./CLAUDE.md`
- `global` → inject into `~/.claude/CLAUDE.md`
- `--force` → replace the existing policy block in place (only between the sentinels)
- `--uninstall` → remove the policy block previously installed by this skill

Parse from `$ARGUMENTS`. Unknown or conflicting tokens → AskUserQuestion; never guess.

## Core Process

| Phase | Goal                         | Details         |
| ----- | ---------------------------- | --------------- |
| 0     | Setup                        | Inline below    |
| 1     | Install / update / uninstall | `phases/run.md` |

### Phase 0: Setup

1. Parse `$ARGUMENTS`: scope (`project`/`global`, default `project`), `--force`, `--uninstall`. Unknown or conflicting token → AskUserQuestion.
1. `task_name` = `<YYYY_MM_DD>_gov-init_<slug>` where `<YYYY_MM_DD>` is today's date (underscores) and `<slug>` is a snake_case summary of the args (e.g. `project`, `global_uninstall`, max 20 chars). On same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `schema_version: 2` as its first line, then `Status: running`, `Phase: 0`, `Started: <ISO>`, `phase_complete: false`, `what_remains: []`, `Scope: <project|global>`, `Force: <bool>`, `Uninstall: <bool>`, `Action: <pending>`, `Target: <resolved path>`.
1. Emit setup block: task_name, scope, resolved target path, mode flags.

The approval gate in `phases/run.md` must run before any write to `CLAUDE.md`. A single run-level confirmation covers the write.

Read `phases/run.md` and proceed to Phase 1.

## Techniques

Techniques: delegated to phase file — see the Phase Overview table above.

## Common Rationalizations

N/A — this is a setup/reference skill, not a discipline gate.

## Red Flags

Red Flags: delegated to phase file — see the Phase Overview table above.

## Verification

Verification: delegated to phase file — after install, grep `CLAUDE.md` for exactly one `mz-gov:governance-policy` start sentinel (zero after uninstall). See `phases/run.md`.

## Error Handling

- **Empty / ambiguous / conflicting argument** → AskUserQuestion; never guess.
- **Missing tooling** — if `${CLAUDE_PLUGIN_ROOT}` is unset or `skills/gov-init/policy/governance-policy.md` is not readable, AskUserQuestion with the failing path.
- **`CLAUDE.md` unreadable or unwritable** → AskUserQuestion with the exact path and error; never fall back silently.
- **Duplicate `mz-gov:governance-policy` sentinels found** (manual edit or prior bug) → stop, report the conflicting lines, ask the user to resolve before re-running.
- **Plugin version unreadable** → use the literal `unknown` for the version tag and note it in the report.

## State Management

State persists to `.mz/task/<task_name>/state.md`. Schema is **v2**: the file's first line is `schema_version: 2`, and alongside the skill's existing `Status` / `Phase` / `Started` keys it carries `phase_complete` (boolean) and `what_remains` (YAML list of strings). Set `phase_complete: false` on phase entry and `true` once the phase's artifacts are written and its gates pass; refresh `what_remains` on every phase transition; `what_remains` MUST be `[]` when `Status: complete`. On reading a `schema_version: 1` or unversioned file, add the missing keys, set `schema_version: 2`, and log the upgrade.

Record `Action:` (`installed` | `replaced` | `skipped` | `removed`) and the resolved `Target:` after Phase 1. Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.
