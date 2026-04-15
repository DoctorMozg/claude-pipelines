# Phase 1: Install / Update / Uninstall

Detailed implementation for install, update, and uninstall flows. Entered from SKILL.md Phase 0 after the setup block is emitted and (for `--target=claudemd` installs) after the approval gate passes.

## Step 1: Resolve target path

| Scope   | Target=rules       | Target=claudemd       |
| ------- | ------------------ | --------------------- |
| project | `.claude/rules/`   | `./CLAUDE.md`         |
| global  | `~/.claude/rules/` | `~/.claude/CLAUDE.md` |

- `target=rules`: create target directory if missing.
- `target=claudemd`: if file missing and not `--uninstall`, flag `will_create=true` for the approval gate.

## Step 2: Detect project context

Scan working directory for language/tooling signals:

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

In `global` scope: skip detection; select all rules (the user wants them everywhere).

## Step 3: Select rules

Bundled at `${CLAUDE_PLUGIN_ROOT}/skills/init-rules/rules/`.

**Universal (always):**

- `code-quality.md`
- `edit-safety.md`
- `self-evaluation.md`
- `context-safety.md`
- `coding-standards.md`
- `agent-workflow.md`
- `housekeeping.md`

**Conditional:**

| Condition                        | Rule file                     |
| -------------------------------- | ----------------------------- |
| `git` detected                   | `git-conventions.md`          |
| `.pre-commit-config.yaml` exists | `pre-commit-conventions.md`   |
| `python` detected                | `python-conventions.md`       |
| `python` detected                | `strict-typing-python.md`     |
| `typescript` detected            | `strict-typing-typescript.md` |

## Step 4: Apply selected rules

Branch on `--target` and `--uninstall`.

### 4a. Install to rules directory — `--target=rules`, no `--uninstall`

For each selected rule:

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/init-rules/rules/<filename>`.
1. If `<target>/<filename>` exists and not `--force`: skip, record `Skipped`.
1. If `<target>/<filename>` exists and `--force`: overwrite, record `Replaced`.
1. Otherwise: write, record `Installed`.

### 4b. Inject into CLAUDE.md — `--target=claudemd`, no `--uninstall`

**Approval gate.** Before any write, call AskUserQuestion with:

- Resolved target path
- File state (`create-new` / `modify-existing`)
- Per-rule action preview: `append` | `replace` (only under `--force`) | `skip` (block exists, no `--force`)

Proceed only on explicit approval. A single run-level confirmation covers all subsequent writes in the run.

**Sentinel format.** Each rule is wrapped:

```
<!-- mz-rule:<id> v=<plugin-version> start -->
<!-- source: <filename>[ | scope: <glob>[, <glob>...]] -->
<rule-body>
<!-- mz-rule:<id> end -->
```

- `<id>` = rule filename without `.md`.
- `<plugin-version>` = read from `${CLAUDE_PLUGIN_ROOT}/../plugin.json` → `version`. If unreadable, use literal `unknown`.
- `source` comment records the original filename; if the rule has `paths:` frontmatter, append `| scope: <glob>` (comma-join multiple globs).
- `<rule-body>` = rule file content with YAML frontmatter stripped. If the body contains any H1 heading (`# `), demote to H2 before injection. H2 and below pass through verbatim.

**Per-rule procedure:**

1. If CLAUDE.md missing, create it with a minimal header:

   ```
   # Project Rules

   <!-- This file is partially managed by mz-dev-base init-rules. Sentinel-wrapped blocks below are maintained automatically; content outside them is user-authored. -->
   ```

   Use `# Project Rules` for project scope, `# Global Rules` for global. Never overwrite an existing header.

1. Grep CLAUDE.md for the start sentinel of `<id>`.

1. **Absent** → append a blank line, then the sentinel block, at end of file. Record `Installed`.

1. **Present, no `--force`** → skip, record `Skipped`.

1. **Present, `--force`** → replace content between the matching start and end sentinels in place, preserving everything outside the block. Record `Replaced`.

### 4c. Uninstall — `--uninstall`

**Target=rules:**

1. Enumerate candidate rule filenames using the same Step 3 selection logic.
1. For each: if `<target>/<filename>` exists AND the filename is in the known bundled rule set, delete and record `Removed`.
1. Never delete files in the rules directory that are not bundled by this skill.

**Target=claudemd:**

1. Approval gate — list every `<!-- mz-rule:<id>` sentinel pair found in the file; confirm before removing.
1. For each matching pair: remove the block plus one adjacent blank line to avoid accumulating gaps.
1. Never delete CLAUDE.md itself, even if it ends up containing only the managed header.

## Step 5: Report

Mode-specific summary.

**Rules-file mode:**

```
Rules installed to <target>:
  ✓ code-quality.md
  ✓ python-conventions.md (detected: pyproject.toml)
  ⊘ git-conventions.md (exists, use --force)

Detected: python, git
Installed: 8  Replaced: 0  Skipped: 1
```

**CLAUDE.md mode:**

```
CLAUDE.md: <resolved path> (created|modified)
  + appended: code-quality, edit-safety
  ~ replaced: python-conventions (--force)
  ⊘ skipped: git-conventions (block exists)

Detected: python, git
Appended: 7  Replaced: 1  Skipped: 1
```

**Uninstall:**

```
Removed from <target>:
  - code-quality (block|file)
  - python-conventions (block|file)

Removed: N
```

## Sentinel Format Reference

Exact line shape — re-runs and uninstall depend on it.

```
<!-- mz-rule:<id> v=<version> start -->
<!-- source: <filename>[ | scope: <glob>[, <glob>...]] -->
<body>
<!-- mz-rule:<id> end -->
```

Detection rules:

- Start sentinel regex: `<!-- mz-rule:<id> v=\S+ start -->`.
- End sentinel regex: `<!-- mz-rule:<id> end -->`.
- Version in the start sentinel is informational (enables future upgrade diffing); detection matches on `<id>` only.
- One block per `<id>`. If duplicates exist (manual edit or prior bug), stop and surface an error — do not guess which to replace.

## Techniques

- **Stack detection**: manifest files + language-extension globs before rule selection.
- **Conditional mapping**: look up in the Step 3 table; never invent rules.
- **Idempotent writes**: honor `--force`; never silently clobber.
- **Sentinel-bounded edits** (claudemd mode): detection via start-sentinel grep, replacement bounded by matching end sentinel. Preserve all content outside the block.
- **Frontmatter stripping**: on inject, remove YAML frontmatter and demote any stray H1 to H2 so CLAUDE.md stays single-rooted.
- **Approval gate** (claudemd mode): always ask once before the first write; never modify CLAUDE.md silently.

## Red Flags

- You invented rule files instead of reading the Step 3 table.
- You copied rules to a non-standard location.
- You skipped stack detection.
- (claudemd mode) You modified CLAUDE.md without the approval gate.
- (claudemd mode) You replaced content outside sentinel boundaries.
- (claudemd mode) You omitted the version tag in the start sentinel.
- (uninstall) You deleted rule files or CLAUDE.md blocks you did not author.

## Verification

Print the mode-appropriate Step 5 summary.

- **Rules-file mode**: confirm each recorded filename exists at `<target>/<filename>` (or is absent after uninstall).
- **CLAUDE.md mode**: after writes, grep CLAUDE.md for each injected `<id>` start sentinel — expect exactly one match per installed rule. For uninstall, expect zero matches for removed IDs.
