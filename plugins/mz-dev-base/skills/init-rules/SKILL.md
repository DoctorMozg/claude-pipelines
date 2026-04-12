---
name: init-rules
description: ALWAYS invoke when the user wants to install development rules for a project or globally. Triggers:"init rules","set up rules","install rules","configure coding rules","onboard project".
argument-hint: '[project|global] [--force]'
model: sonnet
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Init Rules

## Overview

Install curated development rules based on detected project context. Scans the working directory for language/tooling signals, selects matching rule files, and writes them to `.claude/rules/` (project) or `~/.claude/rules/` (global).

## When to Use

Triggers: "init rules", "set up rules", "install rules", "configure coding rules", "onboard project".

### When NOT to use

- The user wants to edit rule content itself — open the rule file directly.
- The user wants per-file rule scoping beyond what `paths:` frontmatter supports.
- The target directory is managed by another tool and should not be touched.

## Arguments

- No argument or `project` → install to `.claude/rules/` (project scope)
- `global` → install to `~/.claude/rules/` (user scope)
- `--force` → overwrite existing rule files

Parse the argument from `$ARGUMENTS`.

## Core Process

### Phase 0: Setup

1. Parse `$ARGUMENTS` to determine mode (`project` default, or `global`) and the `--force` flag. Ambiguous tokens → escalate via AskUserQuestion; never guess.
1. `task_name` = `init_rules_<slug>_<HHMMSS>` where `<slug>` is the mode (`project` or `global`) and `<HHMMSS>` is wall-clock time.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Mode: <project|global>`, `Force: <bool>`, `DetectedContexts: []`, `Installed: []`, `Skipped: []`.
1. Emit a visible setup block: `task_name`, target directory, mode, force flag.

### 1. Determine target directory

```
If $ARGUMENTS contains "global":
  target = ~/.claude/rules/
Else:
  target = .claude/rules/
```

Create the target directory if it doesn't exist.

### 2. Detect project context

Scan the working directory for language and tooling signals. Build a list of detected contexts:

| Signal                                                              | Context tag  |
| ------------------------------------------------------------------- | ------------ |
| `*.py`, `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | `python`     |
| `*.ts`, `*.tsx`, `tsconfig.json`                                    | `typescript` |
| `*.js`, `*.jsx`, `package.json`                                     | `javascript` |
| `*.rs`, `Cargo.toml`                                                | `rust`       |
| `*.go`, `go.mod`                                                    | `go`         |
| `*.cpp`, `*.c`, `*.h`, `CMakeLists.txt`                             | `cpp`        |
| `*.java`, `pom.xml`, `build.gradle`                                 | `java`       |
| `.git`                                                              | `git`        |
| `.pre-commit-config.yaml`                                           | `pre-commit` |

### 3. Select rules

Rules are bundled at `${CLAUDE_PLUGIN_ROOT}/skills/init-rules/rules/`.

**Always install (universal rules):**

- `code-quality.md`
- `edit-safety.md`
- `self-evaluation.md`
- `context-safety.md`
- `coding-standards.md`
- `agent-workflow.md`
- `housekeeping.md`

**Conditional rules:**

| Condition                        | Rule file                     |
| -------------------------------- | ----------------------------- |
| `git` detected                   | `git-conventions.md`          |
| `.pre-commit-config.yaml` exists | `pre-commit-conventions.md`   |
| `python` detected                | `python-conventions.md`       |
| `python` detected                | `strict-typing-python.md`     |
| `typescript` detected            | `strict-typing-typescript.md` |

For `global` mode: install ALL rules regardless of detection (the user wants them everywhere).

### 4. Install rules

For each selected rule:

1. Read the rule file from `${CLAUDE_PLUGIN_ROOT}/skills/init-rules/rules/<filename>`
1. Check if `<target>/<filename>` already exists
   - If exists and `--force` not set: skip it, note it was skipped
   - If exists and `--force` set: overwrite
1. Write the rule file to `<target>/<filename>`

### 5. Report

Print a summary:

```
Rules installed to <target>:
  ✓ code-quality.md
  ✓ edit-safety.md
  ✓ python-conventions.md (detected: pyproject.toml)
  ⊘ git-conventions.md (already exists, use --force to overwrite)

Detected contexts: python, git
Skipped: 1 (already exist)
Installed: 8
```

## Techniques

- **Stack detection**: read manifest files and glob language extensions to build a context tag set before selecting rules.
- **Conditional rule mapping**: never invent rules — look them up in the Step 3 table. Python adds both `python-conventions.md` and `strict-typing-python.md`; TypeScript adds `strict-typing-typescript.md`.
- **Idempotent writes**: honor `--force` — skip existing files unless overwrite is explicit. Never silently clobber.
- Do NOT modify existing CLAUDE.md files — only write to the rules/ directory.
- Rule files with `paths:` frontmatter are path-scoped; without frontmatter they load every session.
- If no project signals are found, still install the universal rules.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 17, not discipline. See Rule 17.

## Red Flags

- You invented rule files instead of reading the conditional-rules table in Step 3.
- You copied rules to a non-standard location (not `.claude/rules/` or `~/.claude/rules/`).
- You skipped the stack-detection step and installed a hardcoded rule set.

## Verification

Print the installed-rules summary block from Step 5, listing the target directory, detected contexts, and per-file install/skip status. Confirm each written file exists at `<target>/<filename>`.

## Error Handling

- **Empty / ambiguous argument** (conflicting tokens, unknown mode) → escalate via AskUserQuestion; never guess.
- **Missing tooling** — if `${CLAUDE_PLUGIN_ROOT}` is unset or the bundled `rules/` directory is not readable, escalate via AskUserQuestion with the exact path that failed.
- **Empty detection result** (no project signals found) → still install universal rules; if the target directory is not writable, escalate via AskUserQuestion. Retry the write once after surfacing the permission error; if still failing, escalate.
- Never guess — on any ambiguity (unknown mode, target directory conflict, pre-existing non-rule files) escalate via AskUserQuestion rather than silently overwrite or skip.
