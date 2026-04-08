# Phases 1-2: Setup

Detail for the scope resolution and tooling detection phases of the verify skill.

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
