# Phases 3-6: Execution, Analysis, Diagnosis, and Report

Full detail for the verification and reporting phases of the verify skill. Covers running all detected tools, analyzing test coverage and quality, diagnosing failures, and compiling the final report.

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
- [Phase 6: Report](#phase-6-report)
  - 6.1 Report template
  - 6.2 Verdict logic

______________________________________________________________________

## Phase 3: Execution

### 3.1 Execution order

Run checks in this order. Run independent checks in parallel where possible.

**Wave 1** (parallel — independent of each other):

- Tests (full suite)
- Linter (on scope files)
- Formatter check (on scope files)
- Type checker (on scope files or full project depending on tool)

**Wave 2** (after wave 1, parallel):

- Example/sample scripts

Examples run after the main checks because they may depend on a working build.

### 3.2 Test execution

Run the test suite using the command from `tooling.md`.

**Scoped execution**: if the test framework supports path filtering and scope is narrowed, run scoped tests first, then the full suite:

1. **Scoped run**: `<test command> <test files for scope>` — verifies the code in scope directly
1. **Full run**: `<test command>` — catches regressions outside scope caused by changes in scope

If scope is global/roam, run the full suite once.

**Capture**:

- Exit code (0 = pass, non-zero = fail)
- stdout/stderr (truncate to last 500 lines if longer)
- Individual test results if the framework supports structured output (pytest `--tb=short`, jest `--verbose`)
- Duration
- Count: total tests, passed, failed, skipped, errors

### 3.3 Linter execution

Run the linter on source files in scope.

```bash
<lint command> <scope files or directories>
```

If the linter supports full-project mode and scope is global, run it once on the whole project.

**Capture**:

- Exit code
- Individual findings: file, line, rule, severity, message
- Count: errors, warnings, info
- Duration

### 3.4 Formatter check

Run the formatter in **check mode** (not write mode) to detect unformatted files without modifying them.

| Formatter    | Check command                            |
| ------------ | ---------------------------------------- |
| ruff format  | `ruff format --check <files>`            |
| black        | `black --check <files>`                  |
| prettier     | `prettier --check <files>`               |
| gofmt        | `gofmt -l <files>` (lists unformatted)   |
| rustfmt      | `rustfmt --check <files>`                |
| clang-format | `clang-format --dry-run -Werror <files>` |

**Capture**:

- List of unformatted files
- Count: formatted vs. unformatted
- Duration

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

Write `.mz/task/<task_name>/execution.md`:

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

### 4.1 Dispatch reviewers

Spawn **two agents in parallel** in a single message:

**`pipeline-test-coverage-reviewer`** (model: **sonnet**):

```
Review test coverage for the code in scope.
Read .mz/task/<task_name>/scope.md for source and test file lists.
Read .mz/task/<task_name>/execution.md for test results.
Focus ONLY on files in scope.md. Save to .mz/task/<task_name>/coverage_review.md.
```

**`pipeline-test-quality-reviewer`** (model: **sonnet**):

```
Review test quality for the code in scope.
Read .mz/task/<task_name>/scope.md for the test file list.
Read .mz/task/<task_name>/execution.md for test results.
Focus ONLY on test files in scope.md. Save to .mz/task/<task_name>/quality_review.md.
```

### 4.2 Merge results

After both reviewers complete, read their output files. Extract:

- Coverage verdict: PASS / FAIL
- Quality verdict: PASS / FAIL
- Combined gap count and severity
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

**Test failure diagnosis**:

```
Diagnose why these tests are failing.

## Failed Tests
<list of failed tests with error output from execution.md>

Read .mz/task/<task_name>/scope.md for source and test files.

For each failure: determine root cause (bug in source? test? setup? environment?), category (logic_bug / missing_implementation / test_bug / configuration / environment / flaky), confidence (high/medium/low), and explanation (WHY it fails with file:line). Group tests failing for the same root cause. Do NOT propose fixes — diagnose only.

Save to .mz/task/<task_name>/diagnosis_tests.md:
Per group: affected tests, root cause, category, confidence, explanation with file:line, impact.
Summary: N failures from K root causes, category breakdown.
```

**Type error diagnosis** (when 6+ errors):

```
Diagnose the type errors in this project.

## Type Errors
<list from execution.md>

Read .mz/task/<task_name>/scope.md for source files.

For each error, determine if it's: genuine type mismatch (real bug), missing type stubs (third-party), overly strict config, or systemic pattern. Group by root cause. Do NOT propose fixes.

Save to .mz/task/<task_name>/diagnosis_types.md with same grouped format.
```

Update state phase to `diagnosis_complete`.

______________________________________________________________________

## Phase 6: Report

### 6.1 Report template

Read all artifacts from `.mz/task/<task_name>/`. Compile into a single report using the naming convention from SKILL.md (`test_<YYYY_MM_DD>_<detailed_name><_vN>.md` in `.mz/reports/`):

```markdown
# Verification Report: <scope summary>

**Date**: <timestamp>
**Scope**: <mode> — N source files, M test files, K examples
**Tools**: <test framework>, <linter>, <formatter>, <type checker or "none">

## Verdict: PASS | FAIL

Verdict vocabulary is strictly binary. There is no `PARTIAL`. A run that is green on tests but carries non-critical hygiene issues (lint, format, type, coverage, quality) is still **PASS** — express the remaining issues as `Nit:` or `FYI:` severity findings in the body per the severity rubric. Only elevate to **FAIL** when a blocking issue is present.

<One-paragraph summary: what passed, what failed, most important finding.>

### Scorecard

| Check | Status | Details |
|---|---|---|
| Tests | PASS/FAIL | P passed, F failed, S skipped of T total |
| Linter | CLEAN/WARN/ERROR | E errors, W warnings |
| Formatter | OK/ISSUES | N files need formatting |
| Type Checker | PASS/FAIL/SKIP | E errors (or "not configured") |
| Examples | PASS/FAIL/SKIP | N passed, M failed, K skipped |
| Test Coverage | PASS/FAIL | <verdict summary> |
| Test Quality | PASS/FAIL | <verdict summary> |

---

## Test Results

<If all pass: "All N tests passed.">
<If failures, for each failed test:>
- **`<test_name>`** (`<file:line>`) — <error type>: <message>
  - Root cause: <from diagnosis> | Category: <logic_bug / test_bug / config / environment / flaky>
<Include key failure output in fenced code blocks. List skipped tests with reasons.>

## Lint Findings

<If clean: "No lint issues." If findings:>

| File | Line | Rule | Severity | Message |
|---|---|---|---|---|
| `<path>` | N | <rule-id> | error/warning | <message> |

## Formatting

<If clean: "All files formatted." If issues: list unformatted files + fix command.>

## Type Checking

<If not configured: "No type checker configured. Skipped." If clean: "No type errors." If errors: table of file/line/code/message. If diagnosis performed: include root cause groups.>

## Examples & Samples

<If none: "No examples detected." If present:>

| Example | Status | Notes |
|---|---|---|
| `<path>` | PASS/FAIL/SKIP | <failure/skip reason> |

<For failed examples: include error output. For README blocks: line number, language, status.>

## Test Coverage Analysis

<Coverage reviewer verdict. Top coverage gaps:>
- **`<file:function>`** — <what's untested, risk level>
<Well-covered areas acknowledgment.>

## Test Quality Analysis

<Quality reviewer verdict. Top quality issues:>
- **`<test_file:test_name>`** — <category>: <what's wrong>
<Well-written tests acknowledgment.>

---

## Summary

### What's working
<Bulleted list of clean passes>

### What needs attention
<Ranked by severity — most impactful first>

### Recommendations
<Prioritized fix list based on all findings>
```

### 6.2 Verdict logic

The overall verdict follows this logic:

| Condition                                                    | Verdict                                                                                                                     |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| All checks PASS, coverage PASS, quality PASS                 | **PASS**                                                                                                                    |
| Tests PASS but lint/format/type/coverage/quality have issues | **PASS** with a Nit-severity finding for each hygiene issue                                                                 |
| Any test failure                                             | **FAIL**                                                                                                                    |
| Examples fail                                                | **FAIL** (or **PASS** with a Nit-severity FYI if failures are demonstrably environment-specific and not reproducible in CI) |

Present the verdict and a one-paragraph summary to the user after writing the report. Include the path to the full report.
