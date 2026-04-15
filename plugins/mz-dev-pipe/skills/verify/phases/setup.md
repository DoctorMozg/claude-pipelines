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

Dispatch a `pipeline-tooling-detector` agent (model: **haiku**):

```
Detect project tooling and write the result to:
output_path: .mz/task/<task_name>/tooling.md
```

Read `.mz/task/<task_name>/tooling.md` when done.

**If the Test command field is "none detected"**: ask the user how to run tests via AskUserQuestion. Do not skip tests.

### 2.5 Detect example runners (inline)

Check for runnable example/sample files not covered by the standard test framework:

- Detect directories: `examples/`, `example/`, `samples/`, `sample/`, `docs/examples/`
- If scope is global/roam, check all examples. If scope is narrowed, only check examples that reference files in scope.
- For Python scripts: check for `if __name__ == "__main__"` or shebang
- For JS/TS scripts: check for direct execution or npm scripts
- For shell scripts: check for shebang and execute permission
- Detect README code blocks with fenced language tags that look runnable (not pseudocode or config snippets)

Append to `.mz/task/<task_name>/tooling.md`:

```markdown
## Examples
- Runnable scripts: N
- README code blocks: M (runnable: K)
- Execution method: <how to run them>
```

Update state phase to `tooling_detected`.
