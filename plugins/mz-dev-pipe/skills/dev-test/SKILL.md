---
name: dev-test
description: Deep verification pipeline — runs tests, linters, formatters, type checkers, analyzes test coverage and quality, checks examples/samples, and diagnoses failures. Produces a comprehensive pass/fail report. Provide scope as the argument.
argument-hint: [scope:branch|global|working] [optional focus — e.g. "src/auth/", "test_payments.py", "check examples work"]
allowed-tools: Agent, Bash, Read, Write, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Verification Pipeline

You orchestrate a deep verification pass that checks whether code in scope is correct, clean, well-tested, and functional. This pipeline reports findings — it does NOT auto-fix anything. The user decides what to fix based on the report.

## Input

- `$ARGUMENTS` — Optional scope and focus. Any combination of:
  - **Path/glob**: `"src/auth/"`, `"tests/test_payments.py"` — which files to verify
  - **Free-text focus**: `"check examples work"`, `"verify the API layer"` — what to focus on
  - **Combined**: `"src/payments/ check all edge cases are tested"`

If empty, verify the entire project (roam mode with standard exclusions).

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, >5000 LOC).                                                                                           |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): use path/glob detection from argument, or roam the entire project if empty.

The `scope:` parameter determines **which source files** are under verification. Tests always run fully (not filtered by scope) to catch regressions. Coverage and quality analysis focus on code within scope.

## Constants

- **TASK_DIR**: `.mz/task/` — working artifacts under `.mz/task/<task_name>/`
- **MAX_RESEARCHERS**: 3 — for failure diagnosis and coverage/quality review

## Phase Overview

| #   | Phase                       | Reference          | Loop? |
| --- | --------------------------- | ------------------ | ----- |
| 0   | Setup                       | inline below       | —     |
| 1   | Scope Resolution            | inline below       | —     |
| 2   | Tooling Detection           | inline below       | —     |
| 3   | Execution                   | `phases/checks.md` | —     |
| 4   | Coverage & Quality Analysis | `phases/checks.md` | —     |
| 5   | Failure Diagnosis           | `phases/checks.md` | —     |
| 6   | Report                      | `phases/checks.md` | —     |

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse argument

Split `$ARGUMENTS` (after removing `scope:` parameter) into:

- **Path-like tokens**: globs, directories, file paths
- **Focus tokens**: everything else — the user's focus area or question

### 0.2 Derive task name

Short snake_case name (max 30 chars).
Examples:

- `""` → `test_full_project`
- `"scope:branch"` → `test_branch_changes`
- `"src/auth/"` → `test_src_auth`
- `"check examples work"` → `test_examples`

### 0.3 Create task directory and state

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Test: <scope + focus summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
```

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

______________________________________________________________________

## Phase 1: Scope Resolution

Resolve the argument into two file lists:

**Source files in scope** (what's being verified):

- **`scope:` parameter given**: use the git-derived file list, applying standard exclusions (vendored, generated, lock files)
- **Path-like tokens**: expand via Glob or directory walk
- **Free-text only**: spawn a `pipeline-researcher` agent (model: **sonnet**) to identify matching files. If low confidence, ask the user.
- **Empty**: roam — all source files minus `.gitignore`, vendored deps, generated code

**Test files for scope** (tests that exercise the source files):

- For each source file in scope, find its corresponding test file(s) by convention:
  - `src/foo.py` → `tests/test_foo.py`, `test/test_foo.py`, `src/foo_test.py`
  - `src/foo.ts` → `src/foo.test.ts`, `src/foo.spec.ts`, `__tests__/foo.test.ts`
  - `src/foo.go` → `src/foo_test.go`
  - `src/foo.rs` → inline `#[cfg(test)]` modules, or `tests/` directory
- Also include any test files that import/reference source files in scope (grep for imports)

**Example/sample files** (checked if present):

- Detect directories: `examples/`, `example/`, `samples/`, `sample/`, `docs/examples/`
- If scope is global/roam, check all examples. If scope is narrowed, only check examples that reference files in scope.
- Detect README code blocks that contain executable snippets (fenced blocks with language tags)

Write `.mz/task/<task_name>/scope.md`:

```markdown
# Scope
- Mode: <branch / global / working / path / roam>
- Source files: N
- Test files found: M
- Example/sample files: K
- README code blocks: J
- File list:
  ## Source files
  <list>
  ## Test files
  <list>
  ## Examples/samples
  <list>
```

Update state phase to `scope_resolved`.

______________________________________________________________________

## Phase 2: Tooling Detection

Examine the project to identify all verification tools. This phase runs entirely inline — no subagents.

### 2.1 Detect test framework

Search for configuration in: `pyproject.toml`, `setup.cfg`, `package.json`, `Cargo.toml`, `go.mod`, `CMakeLists.txt`, `Makefile`, `Gemfile`, `build.gradle`, `pom.xml`.

| Language | Common frameworks     | Detection                                                              |
| -------- | --------------------- | ---------------------------------------------------------------------- |
| Python   | pytest, unittest      | `[tool.pytest]` in pyproject.toml, `pytest` in deps, `test_*.py` files |
| JS/TS    | jest, vitest, mocha   | `jest` or `vitest` in package.json scripts/deps, config files          |
| Go       | built-in `go test`    | `go.mod` exists, `_test.go` files present                              |
| Rust     | built-in `cargo test` | `Cargo.toml` exists                                                    |
| C/C++    | gtest, catch2, ctest  | `CMakeLists.txt` with `enable_testing()`, gtest in deps                |
| Java     | JUnit, TestNG         | `@Test` annotations, test deps in build file                           |

### 2.2 Detect linters

Search for: `.pre-commit-config.yaml`, `ruff.toml`, `pyproject.toml [tool.ruff]`, `.eslintrc*`, `eslint.config.*`, `.golangci.yml`, `clippy` in Cargo config, `.clang-tidy`, `tslint.json`.

### 2.3 Detect formatters

Search for: `ruff format` config, `black` in deps, `prettier` in deps, `gofmt`/`goimports`, `rustfmt`, `clang-format`.

### 2.4 Detect type checkers

Search for: `mypy` in deps or `[tool.mypy]` config, `tsconfig.json` (implies `tsc --noEmit`), `pyright` config, type stubs. **Only detect type checkers the project already has configured** — never add new ones.

### 2.5 Detect example runners

For example/sample files:

- Python scripts: check for `if __name__ == "__main__"` or shebang
- JS/TS scripts: check for direct execution or npm scripts
- Shell scripts: check for shebang and execute permission
- README code blocks: identify language and whether they're runnable (not just snippets)

Write `.mz/task/<task_name>/tooling.md`:

```markdown
# Detected Tooling
## Tests
- Framework: <name>
- Command: `<command>`
- Scoped command: `<command to run only tests for scope>` (if supported)

## Linter
- Tool: <name> (or "none detected")
- Command: `<command>`

## Formatter
- Tool: <name> (or "none detected")
- Command: `<command>` (check mode, not write mode)

## Type Checker
- Tool: <name> (or "none detected — project has no type checking configured")
- Command: `<command>`

## Examples
- Runnable scripts: N
- README code blocks: M (runnable: K)
- Execution method: <how to run them>
```

**If no test framework is detected**: ask the user how to run tests via AskUserQuestion. Do not skip tests.

Update state phase to `tooling_detected`.

______________________________________________________________________

## Phase 3: Execution

Run all detected tools and capture results.

**See `phases/checks.md` → Phase 3** for execution order, output capture, and the per-check result format.

Update state phase to `checks_executed`.

______________________________________________________________________

## Phase 4: Coverage & Quality Analysis

Dispatch `pipeline-test-coverage-reviewer` and `pipeline-test-quality-reviewer` agents to analyze tests for code in scope.

**See `phases/checks.md` → Phase 4** for dispatch prompts and result artifacts.

Update state phase to `analysis_complete`.

______________________________________________________________________

## Phase 5: Failure Diagnosis

If any check in Phase 3 produced failures, dispatch `pipeline-researcher` agents to diagnose root causes.

**See `phases/checks.md` → Phase 5** for the diagnosis dispatch prompt and result artifact.

If all checks passed, skip this phase.

Update state phase to `diagnosis_complete`.

______________________________________________________________________

## Phase 6: Report

Compile all results into a single comprehensive report.

**See `phases/checks.md` → Phase 6** for the full report template.

Write the report to `.mz/reports/` using the naming convention below. Update state to `completed`. Present a summary to the user with the report path.

**Report file naming**: `<skill_type>_<YYYY_MM_DD>_<detailed_name><_vN>.md`

- `skill_type`: `test`
- `YYYY_MM_DD`: current date
- `detailed_name`: snake_case descriptive name derived from scope (e.g., `branch_changes`, `src_auth`, `full_project`)
- `_vN`: version suffix only if a report with the same base name already exists in `.mz/reports/` (check with Glob before writing — append `_v2`, `_v3`, etc.)

Examples: `test_2026_04_06_branch_changes.md`, `test_2026_04_06_src_auth.md`, `test_2026_04_06_full_project_v2.md`

______________________________________________________________________

## Error Handling

- **No test framework detected**: ask the user for a test command. Do not skip.
- **No linter detected**: note it in the report, skip lint checks.
- **No formatter detected**: note it in the report, skip format checks.
- **No type checker configured**: note it in the report, skip type checks. Do NOT suggest adding one.
- **Test command times out**: report timeout with partial output, flag in report.
- **Example script crashes**: capture the error output, include in report, do not retry.
- **Ambiguous scope**: ask the user to clarify.
- **Empty scope**: report and exit.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Per-check results (pass/fail/skip)
- Any issues encountered
