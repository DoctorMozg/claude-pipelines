# Phase 6: Report

Full detail for the report phase of the verify skill: compiling the artifacts from Phases 3-5 into the final report and deciding the verdict.

## 6.1 Report template

Read all artifacts from `<PROJECT_ROOT>/.mz/task/<task_name>/`. Compile into a single report using the naming convention from SKILL.md (`<YYYY_MM_DD>_test_<detailed_name><_vN>.md` in `<PROJECT_ROOT>/.mz/reports/`):

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

## 6.2 Verdict logic

The overall verdict follows this logic:

| Condition                                                    | Verdict                                                                                                                     |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| All checks PASS, coverage PASS, quality PASS                 | **PASS**                                                                                                                    |
| Tests PASS but lint/format/type/coverage/quality have issues | **PASS** with a Nit-severity finding for each hygiene issue                                                                 |
| Any test failure                                             | **FAIL**                                                                                                                    |
| Examples fail                                                | **FAIL** (or **PASS** with a Nit-severity FYI if failures are demonstrably environment-specific and not reproducible in CI) |

Present the verdict and a one-paragraph summary to the user after writing the report. Include the path to the full report.
