---
name: init-rules
description: ALWAYS invoke when the user wants to set up or install development rules for a project or globally. Triggers: "init rules", "set up rules", "install rules", "configure coding rules", "onboard project". Detects project languages and installs relevant coding rules to .claude/rules/ (project) or ~/.claude/rules/ (global).
argument-hint: '[project|global] [--force]'
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Init Rules

Install curated development rules based on project context.

## Arguments

- No argument or `project` → install to `.claude/rules/` (project scope)
- `global` → install to `~/.claude/rules/` (user scope)
- `--force` → overwrite existing rule files

Parse the argument from `$ARGUMENTS`.

## Process

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

| Condition                         | Rule file                   |
| --------------------------------- | --------------------------- |
| `git` detected                    | `git-conventions.md`        |
| `.pre-commit-config.yaml` exists  | `pre-commit-conventions.md` |
| `python` detected                 | `python-conventions.md`     |
| `python` OR `typescript` detected | `strict-typing.md`          |

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

## Important

- Do NOT modify existing CLAUDE.md files — only write to the rules/ directory.
- Rule files with `paths:` frontmatter are path-scoped and only load when Claude works with matching files.
- Rule files without frontmatter load every session unconditionally.
- If no project signals are found (empty directory), still install the universal rules.
