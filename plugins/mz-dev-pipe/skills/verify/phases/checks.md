# Phases 3-5: Execution, Analysis, and Diagnosis

Full detail for the verification phases of the verify skill. Covers running all detected tools, analyzing test coverage and quality, and diagnosing failures. The report is in `phases/report.md`.

## Contents

- [Phase 3: Execution](#phase-3-execution)
  - 3.1 Execution order
  - 3.2 Test execution
  - 3.3 Linter execution
  - 3.4 Formatter check
  - 3.5 Type checker execution
  - 3.6 Example/sample verification
  - 3.7 Write execution artifact
- [Phase 4: Coverage & Quality Analysis](#phase-4-coverage--quality-analysis)
  - 4.1 Dispatch reviewers
  - 4.2 Merge results
- [Phase 5: Failure Diagnosis](#phase-5-failure-diagnosis)
  - 5.1 Triage failures
  - 5.2 Dispatch diagnosticians

______________________________________________________________________

## Phase 3: Execution

### 3.1 Execution order

Run checks in this order. Run independent checks in parallel where possible.

**Wave 1** (parallel — independent of each other):

- Tests (full suite)
- Linter (on scope files)
- Formatter check (on scope files)
- Type checker (on scope files or full project depending on tool)

The three agent-run checks of wave 1 (tests, linter, formatter check) go out together. Emit the pre-dispatch manifest before launching them, and pass each role label as the agent's `description`:

```
Dispatching verification checks — 3 agents in parallel
Purpose: run tests, lint and format checks on scope
- pipeline-test-runner — test suite run
- pipeline-lint-runner — linter on scope files
- pipeline-lint-runner — formatter check on scope files
```

When all three have reported, emit the post-wave rollup before starting wave 2:

```
Wave complete (verification checks) — <returned>/<dispatched> agents returned
- pipeline-test-runner: <STATUS> — <summary, ≤8 words>
- pipeline-lint-runner: <STATUS> — <summary, ≤8 words>
```

An agent that returns no `STATUS:` line is listed as `NO RETURN BLOCK` and counted as not-returned. When 3.2 runs a scoped test run first, the full run that follows is a single dispatch outside this wave.

**Wave 2** (after wave 1, parallel):

- Example/sample scripts

Examples run after the main checks because they may depend on a working build.

### 3.2 Test execution

Dispatch `pipeline-test-runner` agents (model: **haiku**) using the commands from `tooling.md`.

**If scope is narrowed and the Scoped test command is supported**: dispatch two runs in sequence:

Scoped run first:

```
Run scoped tests for the code in scope.
test_command: <Scoped test command from tooling.md, %FILES% replaced with test files from scope.md>
specific_files: <test files from scope.md>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/test_results_scoped.md
```

Then full run:

```
Run the full test suite to catch regressions outside scope.
test_command: <Test command from tooling.md>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/test_results_full.md
```

**If scope is global/roam or scoped command is "not supported"**: dispatch one full run only:

```
Run the full test suite.
test_command: <Test command from tooling.md>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/test_results_full.md
```

Read the resulting artifact(s) when done.

### 3.3 Linter execution

Dispatch a `pipeline-lint-runner` agent (model: **haiku**):

```
Run linter on the source files in scope.
lint_command: <Lint command from tooling.md, or "none detected">
scope_files: <source files from scope.md>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/lint_results.md
```

Read `<PROJECT_ROOT>/.mz/task/<task_name>/lint_results.md`.

### 3.4 Formatter check

Derive the check-mode formatter command from `tooling.md`:

| Formatter    | Check command                            |
| ------------ | ---------------------------------------- |
| ruff format  | `ruff format --check <files>`            |
| black        | `black --check <files>`                  |
| prettier     | `prettier --check <files>`               |
| gofmt        | `gofmt -l <files>` (lists unformatted)   |
| rustfmt      | `rustfmt --check <files>`                |
| clang-format | `clang-format --dry-run -Werror <files>` |

Dispatch a `pipeline-lint-runner` agent (model: **haiku**) with the check-mode command:

```
Check formatting without modifying files.
format_command: <check-mode formatter command derived above, or "none detected">
scope_files: <source files from scope.md>
output_path: <PROJECT_ROOT>/.mz/task/<task_name>/format_results.md
```

Read `<PROJECT_ROOT>/.mz/task/<task_name>/format_results.md`.

### 3.5 Type checker execution

Run the type checker if one was detected. **Skip entirely if no type checker is configured** — do not add or suggest one.

```bash
<type check command>
```

Most type checkers run project-wide (mypy with config, tsc with tsconfig). Run as configured. If the type checker supports path filtering and scope is narrowed, scope it.

**Capture**:

- Exit code
- Individual type errors: file, line, error code, message
- Count: errors, warnings
- Duration

### 3.6 Example/sample verification

For each runnable example/sample detected in `tooling.md`:

**Scripts** (Python, JS, Shell, etc.):

1. Run each script with a timeout of 30 seconds
1. Capture exit code, stdout, stderr
1. Pass = exit code 0 and no unhandled exceptions in stderr
1. Fail = non-zero exit code or exception traceback in stderr

**README code blocks**:

1. Only check blocks that are self-contained and runnable (have all imports, don't require external setup)
1. For Python: extract to a temp file and run with `python <temp>`
1. For shell: extract and run with `bash <temp>`
1. For other languages: skip unless the project has a clear execution method
1. Non-runnable blocks (partial snippets, pseudocode, config examples): verify they reference actual symbols that exist in the codebase (grep for function/class names mentioned)

**Capture per example**:

- File path or README location
- Status: PASS / FAIL / SKIP (with reason for skip)
- stdout/stderr if failed
- Duration

### 3.7 Write execution artifact

Write `<PROJECT_ROOT>/.mz/task/<task_name>/execution.md`:

```markdown
# Execution Results

## Tests
- Command: `<command>` | Status: PASS/FAIL | Duration: Xs
- Results: N total, P passed, F failed, S skipped, E errors
- Failed tests: `test_name` — <summary> (one per line)
- Output (last 200 lines if failed): <fenced code block>

## Linter
- Tool: <name> | Command: `<command>` | Status: CLEAN/WARNINGS/ERRORS
- Findings: E errors, W warnings | Details: `file:line` — <rule>: <message> (one per line)

## Formatter
- Tool: <name> | Command: `<command>` | Status: FORMATTED/UNFORMATTED
- Unformatted files: <list>

## Type Checker
- Tool: <name or "not configured — skipped"> | Command: `<command>` | Status: PASS/FAIL/SKIPPED
- Errors: `file:line` — <error code>: <message> (one per line)

## Examples/Samples
- Total: N (runnable: M, skipped: K) | Status: ALL_PASS/SOME_FAIL/ALL_SKIP
- Per-example table: File | Status | Duration | Notes
```

Update state phase to `checks_executed`.

______________________________________________________________________

## Phase 4: Coverage & Quality Analysis

**Goal**: Assess how well the code in scope is tested — both coverage completeness and test quality.

Only run this phase if tests passed or partially passed (at least some tests ran successfully). If the entire test suite crashed during execution, skip to Phase 5.

### 4.1 Dispatch reviewer

Spawn one agent:

**`pipeline-test-reviewer`** (model: **sonnet** — combined coverage + quality review):

```
Review tests for the code in scope. Cover BOTH axes in one pass:
- Coverage gaps (untested public functions, missing code paths, missing edge cases, untested error paths)
- Quality defects (weak assertions, order dependence, over-mocking, fragility)

Read <PROJECT_ROOT>/.mz/task/<task_name>/scope.md for source and test file lists.
Read <PROJECT_ROOT>/.mz/task/<task_name>/execution.md for test results.
Focus only on files in scope.md.

Return the unified Test Review as markdown in your response — the orchestrator persists to `<PROJECT_ROOT>/.mz/task/<task_name>/test_review.md`.
The review must include both the Coverage section (with gap-count summary) and the Quality section, ending with a single VERDICT line.
```

The reviewer is read-only and returns the review inline. After it returns, the **orchestrator** (not a sub-agent) writes the response to `<PROJECT_ROOT>/.mz/task/<task_name>/test_review.md` via the Write tool before Phase 4.2 reads the file.

### 4.2 Merge results

After the reviewer completes, read its output file. Extract:

- Combined verdict: PASS / FAIL (single line — `Critical:` in either Coverage or Quality forces FAIL)
- Coverage gap count and severity breakdown
- Quality issue count and severity breakdown
- Key findings to surface in the final report

Update state phase to `analysis_complete`.

______________________________________________________________________

## Phase 5: Failure Diagnosis

**Goal**: For any failures in Phase 3, diagnose root causes so the user understands WHY things fail, not just THAT they fail.

If all checks passed, skip this phase entirely.

### 5.1 Triage failures

Group failures by category:

| Category                  | Dispatch?           | Rationale                               |
| ------------------------- | ------------------- | --------------------------------------- |
| Test failures (1-3 tests) | Diagnose inline     | Small enough to analyze directly        |
| Test failures (4+ tests)  | Dispatch researcher | Too many to analyze inline efficiently  |
| Lint errors               | No dispatch         | Lint output is self-explanatory         |
| Format issues             | No dispatch         | File list is sufficient                 |
| Type errors (1-5)         | Diagnose inline     | Usually clear from error message + code |
| Type errors (6+)          | Dispatch researcher | May indicate systemic issue             |
| Example failures          | Diagnose inline     | Usually import/setup issues             |

### 5.2 Dispatch diagnosticians

For categories that need a researcher, spawn `pipeline-researcher` agents (model: **sonnet**). Dispatch in parallel if multiple categories need diagnosis.

When both categories need diagnosis, the two researchers form one wave. Emit the pre-dispatch manifest before spawning them, and pass each role label as the agent's `description`:

```
Dispatching failure diagnosis — 2 agents in parallel
Purpose: diagnose test failures and type errors
- pipeline-researcher — test failure diagnosis
- pipeline-researcher — type error diagnosis
```

**Test failure diagnosis**:

```
Diagnose why these tests are failing.

## Failed Tests
<list of failed tests with error output from execution.md>

Read <PROJECT_ROOT>/.mz/task/<task_name>/scope.md for source and test files.

For each failure: determine root cause (bug in source? test? setup? environment?), category (logic_bug / missing_implementation / test_bug / configuration / environment / flaky), confidence (high/medium/low), and explanation (WHY it fails with file:line). Group tests failing for the same root cause. Do not propose fixes — diagnose only.

Return the diagnosis as markdown **inline in your response** — the orchestrator persists to `<PROJECT_ROOT>/.mz/task/<task_name>/diagnosis_tests.md`. Use this structure:
Per group: affected tests, root cause, category, confidence, explanation with file:line, impact.
Summary: N failures from K root causes, category breakdown.
```

**Type error diagnosis** (when 6+ errors):

```
Diagnose the type errors in this project.

## Type Errors
<list from execution.md>

Read <PROJECT_ROOT>/.mz/task/<task_name>/scope.md for source files.

For each error, determine if it's: genuine type mismatch (real bug), missing type stubs (third-party), overly strict config, or systemic pattern. Group by root cause. Do not propose fixes.

Return the diagnosis as markdown **inline in your response** — the orchestrator persists to `<PROJECT_ROOT>/.mz/task/<task_name>/diagnosis_types.md` using the same grouped format.
```

When both were dispatched, emit the post-wave rollup once both have reported, in the same form as in 3.1 and labeled `failure diagnosis`.

After either diagnostician returns, the orchestrator writes the response to the corresponding artifact via the Write tool before proceeding to Phase 6 in `phases/report.md`.

Update state phase to `diagnosis_complete`.
