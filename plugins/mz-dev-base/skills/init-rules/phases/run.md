# Phase 1: Install / Update / Uninstall

Detailed implementation for install, update, and uninstall flows. Entered from SKILL.md Phase 0 after the setup block is emitted. Every run passes the approval gate in Step 6 before its first write, in both target modes and for uninstall.

## Step 1: Resolve target path

| Scope   | Target=rules       | Target=claudemd       |
| ------- | ------------------ | --------------------- |
| project | `.claude/rules/`   | `./CLAUDE.md`         |
| global  | `~/.claude/rules/` | `~/.claude/CLAUDE.md` |

- `target=rules`: create the target directory at apply time if missing.
- `target=claudemd`: if the file is missing and not `--uninstall`, flag `will_create=true` for the approval gate.
- The settings file path is resolved in `phases/enforce.md` Step 1.

**AGENTS.md guard** (project scope, `will_create=true`). If `./AGENTS.md` exists and there is no `CLAUDE.md`, `.claude/CLAUDE.md`, or `CLAUDE.local.md` in the working directory or any directory above it (`~/.claude/CLAUDE.md` doesn't count), Claude Code currently loads AGENTS.md as the project instructions. A new `./CLAUDE.md` would replace it under the default **Project instructions** setting, and AGENTS.md would stop loading. Ask before going further. This is an input collector, not an approval gate:

- question: `This project uses AGENTS.md, and a new CLAUDE.md would stop Claude Code from loading it. How should the rules go in?`
- header: `AGENTS.md`
- options:
  - **Import AGENTS.md (Recommended)** — create CLAUDE.md with `@AGENTS.md` as its first line, so both load
  - **Use rules mode** — write `.claude/rules/` files instead, which load alongside AGENTS.md
  - **Create CLAUDE.md only** — AGENTS.md stops loading unless Project instructions is set to `claude-md-and-agents-md`

Record the answer in `state.md` → `AgentsMd` as `import`, `rules`, or `claudemd-only`. For `rules`, set `Target: rules` and resolve the target again from the table above.

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

In `global` scope: skip detection and treat every context as present (the user wants the rules everywhere).

## Step 3: Select rules

Bundled at `<SKILL_DIR>/rules/`.

**Universal (always):**

- `code-quality.md`
- `edit-safety.md`
- `self-evaluation.md`
- `context-safety.md`
- `coding-standards.md`
- `agent-workflow.md`
- `housekeeping.md`
- `safety.md`

**Conditional:**

| Condition                        | Rule file                     |
| -------------------------------- | ----------------------------- |
| `git` detected                   | `git-conventions.md`          |
| `.pre-commit-config.yaml` exists | `pre-commit-conventions.md`   |
| `python` detected                | `python-conventions.md`       |
| `python` detected                | `strict-typing-python.md`     |
| `typescript` detected            | `strict-typing-typescript.md` |

**Personal groups (only when chosen in Step 4):**

| Group             | Rule files                                                               | Offered when            | Summary                                                                                                                                              |
| ----------------- | ------------------------------------------------------------------------ | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code style extras | `personal-code-style.md`                                                 | always                  | Logs at decision points, 1–2 line comments, a params object past four parameters, validated public-function input, Python logic grouped into classes |
| Git + C++ style   | `personal-git.md` if `git` detected, `personal-cpp.md` if `cpp` detected | `git` or `cpp` detected | Commit messages of six words or fewer with no AI attribution; `auto` in C++                                                                          |
| Review rituals    | `personal-review.md`                                                     | always                  | Two-perspective review of real tradeoffs; a one- or two-sentence bug autopsy after each fix                                                          |

These files carry one person's taste rather than broadly evidenced defaults, so they install only on an explicit choice.

## Step 4: Choose personal groups

Skip on `--uninstall`.

A group counts as installed when any of its files already exists at the target (rules mode) or any of its ids has a start sentinel in CLAUDE.md (claudemd mode). Installed groups stay selected and get the normal skip or replace handling in Step 5. Ask only about the offered groups that are not installed; if none remain, skip the question.

This is an input collector, not an approval gate. Call AskUserQuestion with `multiSelect: true`:

- question: `Which personal preference groups should be installed too?`
- header: `Personal`
- one option per remaining group: label = group name, description = its Summary from the Step 3 table
- a last option: **None** — install no personal preferences

Add the chosen groups' files to the selection and record the group names in `state.md` → `PersonalGroups`. An answer of **None**, or no selection, adds nothing.

## Step 5: Build the plan

**Install.** For each selected rule, compare against the target:

| Target state                        | Action                                               |
| ----------------------------------- | ---------------------------------------------------- |
| absent                              | install                                              |
| present, same version               | skip, or replace with `--force`                      |
| present, older version              | upgrade                                              |
| present, newer version              | skip and report                                      |
| present, unmarked (rules mode only) | skip and report as legacy, or replace with `--force` |

In rules mode "present" means `<target>/<filename>` exists and its version is the `v=` of its marker line; in claudemd mode it means the start sentinel for `<id>` exists and carries the version. Compare versions as semver; `unknown` counts as older.

**Stale content (install only).** Read `<SKILL_DIR>/references/retired.md`.

1. Retired ids: a claudemd start sentinel for a retired id → `retire` (block). In rules mode, `<target>/<id>.md` with a marker line → `retire` (file). Without a marker, report it as legacy, or `retire` it with `--force`.
1. Hand-written copies, in both modes: read the scope's CLAUDE.md (`./CLAUDE.md` for project, `~/.claude/CLAUDE.md` for global). Outside sentinel blocks, find each heading that matches a Sections row as `retired.md` describes. A section runs from its heading to the next heading of the same or higher level. Propose it as `hand-remove` when its Now in is `retired`, or when the rule named there is selected in this run. A parent heading left with no content once its subsections go is proposed too.
1. Never propose text inside sentinel blocks, and leave everything outside the proposed sections as it is.

**Uninstall.** Rules mode lists every bundled or retired rule filename that exists at the target, personal files included. Claudemd mode lists every `<!-- mz-rule:<id>` sentinel pair in CLAUDE.md.

**Settings.** Read `phases/enforce.md` and run its Step 1 to add the settings section: entries to add or remove, and the limits it says to state.

## Step 6: Approval gate

**This orchestrator** (not a subagent) presents this gate. This step is interactive and must not be delegated.

**Surface 1 — emit the plan message.** Output the plan as a normal markdown chat message:

```
## Install plan ready for review — init-rules

Rules target: <resolved path> (<create-new | create-new, imports AGENTS.md | modify-existing>)
Detected: <context tags>
Personal groups: <chosen groups | none>

Rules:
<one line per rule: <id> — install | replace (--force) | upgrade <old> → <new> | skip (<reason>)>

Stale content:
<one line per retired id: <id> — retire (block | file)>
<one line per legacy file: <filename> — unmarked, left alone (use --force to replace)>
<per hand-written section: <CLAUDE.md path>:<first>-<last> "<heading>" — remove (now in <rule id> | retired), followed by the section text verbatim in a quote block>

Settings: <settings file path> (<create-new | modify-existing> | skipped: <reason>)
<one line per entry: <entry> — add | already present>
<the limits from phases/enforce.md>

---
**Approve** → apply every write above  ·  **Reject** → abort, nothing written  ·  reply with feedback to revise
```

On `--uninstall`, title it `Uninstall plan ready for review`, list `<id> — remove (block | file)` per rule and `<entry> — remove` per settings entry.

**Surface 2 — call AskUserQuestion.** A short selector — do not re-embed the plan in the question body:

- question: `The plan above is ready for review.`
- options: **Approve** — apply every write · **Reject** — abort, nothing written

**Response handling**:

- **Approve** → proceed to Step 7. This one confirmation covers every write in the run.
- **Reject** → update state to `aborted_by_user`, stop. Do not write anything.
- **Any other reply (feedback)** → apply it (for example drop a rule, a personal group, or a settings entry), rebuild the plan, re-emit the full updated plan message from scratch, and re-present the selector. Repeat until the user approves or rejects.

## Step 7: Apply

### 7a. Rules directory — `--target=rules`, no `--uninstall`

For each rule in the approved plan:

1. Read `<SKILL_DIR>/rules/<filename>` and add the marker line `<!-- mz-rule:<id> v=<plugin-version> -->` right after the YAML frontmatter, or as the first line when there is none. `<plugin-version>` comes from the same place as in 7b.
1. `install` → write `<target>/<filename>`, record `Installed`.
1. `replace` → overwrite `<target>/<filename>`, record `Replaced`.
1. `upgrade` → overwrite `<target>/<filename>`, record `Upgraded`.
1. `retire` → delete `<target>/<id>.md`, record `Retired`.
1. `skip` → leave the file, record `Skipped` with the reason.

### 7b. CLAUDE.md — `--target=claudemd`, no `--uninstall`

**Sentinel format.** Each rule is wrapped:

```
<!-- mz-rule:<id> v=<plugin-version> start -->
<!-- source: <filename>[ | scope: <glob>[, <glob>...]] -->
<rule-body>
<!-- mz-rule:<id> end -->
```

- `<id>` = rule filename without `.md`.
- `<plugin-version>` = read from `<PLUGIN_ROOT>/plugin.json` → `version`. If unreadable, use literal `unknown`.
- `source` comment records the original filename; if the rule has `paths:` frontmatter, append `| scope: <glob>` (comma-join multiple globs).
- `<rule-body>` = rule file content with YAML frontmatter stripped. If the body contains any H1 heading (`# `), demote to H2 before injection. H2 and below pass through verbatim.

**Per-rule procedure:**

1. If CLAUDE.md is missing, create it with a minimal header. When Step 1 recorded `AgentsMd: import`, put `@AGENTS.md` and a blank line above the header:

   ```
   # Project Rules

   <!-- This file is partially managed by mz-dev-base init-rules. Sentinel-wrapped blocks below are maintained automatically; content outside them is user-authored. -->
   ```

   Use `# Project Rules` for project scope, `# Global Rules` for global. Never overwrite an existing header.

1. `install` → append a blank line, then the sentinel block, at end of file. Record `Installed`.

1. `replace` or `upgrade` → replace everything from the start sentinel through the end sentinel in place with the new block, preserving everything outside it. Record `Replaced` or `Upgraded`.

1. `retire` → remove the block plus one adjacent blank line. Record `Retired`.

1. `skip` → leave the block, record `Skipped` with the reason.

### 7c. Uninstall — `--uninstall`

**Target=rules:** delete each file in the approved plan and record `Removed`. Never delete files in the rules directory whose names are neither bundled nor listed as retired in `references/retired.md`.

**Target=claudemd:** remove each approved sentinel pair plus one adjacent blank line, so gaps don't accumulate, and record `Removed`. Never delete CLAUDE.md itself, even if it ends up containing only the managed header.

### 7d. Settings

Unless the settings section was skipped or has nothing to add or remove, run `phases/enforce.md` Step 2 (install) or Step 3 (uninstall) with the approved entries.

### 7e. Hand-written copies

Re-read the scope's CLAUDE.md, then delete the approved `hand-remove` ranges from the bottom of the file up, so earlier line numbers stay valid. Before deleting a range, confirm its first line is still the heading shown at the gate; if the file changed, stop and AskUserQuestion with the mismatch. Collapse any run of blank lines the deletion leaves to one. Record each removed heading in `HandRemoved`.

## Step 8: Report

Mode-specific summary, followed by the settings lines.

**Rules-file mode:**

```
Rules installed to <target>:
  ✓ code-quality.md
  ✓ python-conventions.md (detected: pyproject.toml)
  ✓ personal-review.md (personal: Review rituals)
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

**Settings (all modes):**

```
Settings: <settings file> (created|modified|unchanged|skipped: <reason>)
  + permissions.ask Bash(git push *)
  = attribution (already present)
```

**Stale content (install):**

```
Stale content:
  ↑ upgraded: code-quality 0.49.0 → 0.50.0
  - retired: memory-hygiene (block|file)
  - hand-removed from <CLAUDE.md path>: "Phased Execution", "Bug Autopsy"
  ? legacy, left alone: housekeeping.md (unmarked, use --force)
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
- Detection matches on `<id>`; the version decides between skip, upgrade, and report in Step 5.
- One block per `<id>`. If duplicates exist (manual edit or prior bug), stop and surface an error — do not guess which to replace.

Rules-mode files carry one marker line instead, right after the frontmatter or first when there is none:

```
<!-- mz-rule:<id> v=<version> -->
```

Marker regex: `^<!-- mz-rule:<id> v=(\S+) -->$`. A file at the target without it is unmarked legacy content.

## Techniques

- **Stack detection**: manifest files + language-extension globs before rule selection.
- **Conditional mapping**: look up in the Step 3 tables; never invent rules.
- **Personal opt-in**: personal files install only through the Step 4 choice, never by detection alone.
- **Idempotent writes**: honor `--force`; never silently clobber.
- **Sentinel-bounded edits** (claudemd mode): detection via start-sentinel grep, replacement bounded by matching end sentinel. Preserve all content outside the block.
- **Frontmatter stripping**: on inject, remove YAML frontmatter and demote any stray H1 to H2 so CLAUDE.md stays single-rooted.
- **One gate per run**: rules and settings changes are approved together, before the first write.

## Red Flags

- You invented rule files instead of reading the Step 3 tables.
- You installed a personal file the user did not choose in Step 4.
- You copied rules to a non-standard location.
- You skipped stack detection.
- You wrote rules, CLAUDE.md, or settings before the Step 6 approval.
- (claudemd mode) You replaced content outside sentinel boundaries.
- (claudemd mode) You omitted the version tag in the start sentinel.
- (rules mode) You wrote a rule file without its marker line.
- (stale) You removed a hand-written section that was not shown verbatim at the gate, or touched text inside a sentinel block during the hand-written scan.
- (stale) You proposed removing a section whose Now in rule is not selected in this run.
- (settings) You changed or removed a settings entry that is not in the `phases/enforce.md` fragment.
- (uninstall) You deleted rule files or CLAUDE.md blocks you did not author.

## Verification

Print the mode-appropriate Step 8 summary.

- **Rules-file mode**: confirm each recorded filename exists at `<target>/<filename>` with a marker line carrying the current version (or is absent after uninstall or retirement).
- **CLAUDE.md mode**: after writes, grep CLAUDE.md for each injected `<id>` start sentinel — expect exactly one match per installed rule, carrying the current version. For uninstall and retirement, expect zero matches for removed IDs.
- **Hand-written copies**: none of the `HandRemoved` headings remain outside sentinel blocks, and the line count dropped by the size of the approved ranges, give or take collapsed blank lines.
- **Settings**: run the checks in `phases/enforce.md` Verification.
