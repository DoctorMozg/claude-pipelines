---
name: init-rules
description: ALWAYS invoke when the user wants to install development rules for a project or globally. Triggers:"init rules","set up rules","install rules","configure coding rules","onboard project".
argument-hint: '[project|global] [--target=rules|claudemd] [--force] [--uninstall]'
model: sonnet
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Init Rules

## Overview

Install curated development rules based on detected project context. Two delivery modes:

- `--target=rules` (default) — write rule files into `.claude/rules/` (project) or `~/.claude/rules/` (global). Files with `paths:` frontmatter stay path-scoped.
- `--target=claudemd` — inject rule content directly into `./CLAUDE.md` (project) or `~/.claude/CLAUDE.md` (global), wrapped in sentinel blocks for idempotent re-runs and clean uninstall.

## When to Use

Triggers: "init rules", "set up rules", "install rules", "configure coding rules", "onboard project".

### When NOT to use

- The user wants to edit rule content itself — open the rule file directly.
- The user wants per-file rule scoping — use `--target=rules`; claudemd mode cannot path-scope.
- The target directory or CLAUDE.md is managed by another tool and should not be touched.

## Arguments

- `project` (default) → scope to working directory
- `global` → scope to `~/.claude/`
- `--target=rules` (default) → write as individual rule files
- `--target=claudemd` → inject into CLAUDE.md with sentinel blocks
- `--force` → overwrite existing rule files / replace existing sentinel blocks
- `--uninstall` → remove rules previously installed by this skill (mode-aware)

Parse from `$ARGUMENTS`. Unknown or conflicting tokens → AskUserQuestion; never guess.

## Core Process

| Phase | Goal                         | Details         |
| ----- | ---------------------------- | --------------- |
| 0     | Setup + user approval        | Inline below    |
| 1     | Install / update / uninstall | `phases/run.md` |

### Phase 0: Setup

1. Parse `$ARGUMENTS`: scope (`project`/`global`), target (`rules`/`claudemd`), `--force`, `--uninstall`. Unknown token → AskUserQuestion.
1. `task_name` = `<YYYY_MM_DD>_init_rules_<scope>_<target>` where `<YYYY_MM_DD>` is today's date (underscores); on same-day collision append `_v2`, `_v3`.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO>`, `Scope: <project|global>`, `Target: <rules|claudemd>`, `Force: <bool>`, `Uninstall: <bool>`, `DetectedContexts: []`, `Installed: []`, `Replaced: []`, `Skipped: []`, `Removed: []`.
1. Emit setup block: task_name, resolved target path, mode flags.

For `--target=claudemd` installs, the approval gate in Phase 1 Step 4b must run before any write. A single run-level confirmation covers all subsequent writes in the run.

Read `phases/run.md` and proceed to Phase 1.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill.

## Red Flags

Red Flags: delegated to phase files — see Phase Overview table above.

## Verification

Verification: delegated to phase files — see Phase Overview table above.

## Error Handling

- **Empty / ambiguous argument** → AskUserQuestion; never guess.
- **Missing tooling** — if `${CLAUDE_PLUGIN_ROOT}` is unset or the bundled `rules/` directory is not readable, AskUserQuestion with the failing path.
- **No detected contexts** → still install universal rules; if target not writable, retry once then AskUserQuestion.
- **CLAUDE.md unreadable or unwritable** → AskUserQuestion with the exact path and error; do not fall back silently.
- **Duplicate sentinel IDs found in CLAUDE.md** (manual edit or prior bug) → stop, report the conflicting lines, ask the user to resolve before re-running.
- **Plugin version unreadable** → use literal `unknown` for the version tag and note it in the report.
- Never guess — any ambiguity escalates via AskUserQuestion rather than silent overwrite or skip.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- `Status:` `running` | `complete` | `aborted_by_user` | `failed`
- `Phase:` current phase number
- `DetectedContexts:` list of detected language/tooling tags
- `Installed:` / `Replaced:` / `Skipped:` / `Removed:` filenames or rule ids touched in this run

Never rely on conversation memory for cross-phase state — context compaction destroys specific paths and decisions.
