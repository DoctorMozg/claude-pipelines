---
name: investigate
description: ALWAYS invoke when the user wants to verify a hypothesis, check suspected behavior, or prove/disprove an issue without fixing it. Triggers: "investigate X", "check if Y", "verify whether", "is X actually doing Y", "prove/disprove".
argument-hint: [scope:branch|global|working] <hypothesis — suspected bug, possible issue, or behavior to verify>
model: sonnet
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Hypothesis Investigation Pipeline

## Overview

You orchestrate a hypothesis-driven investigation: analyze the codebase against a suspected issue, run domain research when the hypothesis involves complex external behavior, write exploratory tests to prove or disprove the hypothesis, and report findings with a verdict. No code fixes — output is a report only.

## When to Use

Invoke when the user wants a suspected bug, behavior, regression, or architectural doubt verified without modifying production code. Trigger phrases: "investigate X", "check if Y", "verify whether", "is X actually doing Y", "prove/disprove".

### When NOT to use

- The user has already confirmed the bug and wants a fix — use `debug` instead.
- The user wants to understand how code works without a specific hypothesis — use `explain` instead.
- The hypothesis is a vague wish ("make it faster") with no concrete claim to test.

## Input

- `$ARGUMENTS` — The hypothesis. Accepts any of:
  - Suspected bug: "I think the caching layer doesn't invalidate on concurrent writes"
  - Behavioral question: "does the retry logic actually back off exponentially?"
  - Possible regression: "the auth middleware might not handle expired refresh tokens"
  - Performance concern: "the N+1 query in user listing might be hitting production"
  - Architecture doubt: "I'm not sure the event bus guarantees ordering"

If empty, ask the user what they want investigated.

## Scope Parameter

See [`skills/shared/scope-parameter.md`](../shared/scope-parameter.md) for the canonical scope modes (`branch`, `global`, `working`) and their git commands. Document any skill-specific overrides or restrictions below this line.

- **Default** (no `scope:`): all files in the project are eligible for investigation.
- The `scope:` parameter controls **where to focus the investigation**. Tests are always placed in the project's standard test location regardless of scope.

## Constants

- **MAX_RESEARCH_AGENTS**: 3 — max parallel domain researchers
- **MAX_TEST_RETRIES**: 2 — max re-dispatches for broken exploratory tests
- **TASK_DIR**: `.mz/task/` in the project root

## Core Process

### Phase Overview

| Phase | Goal                          | Details                     |
| ----- | ----------------------------- | --------------------------- |
| 0     | Setup                         | Inline below                |
| 1     | Code analysis                 | `phases/research.md`        |
| 2     | Domain research (conditional) | `phases/research.md`        |
| 3     | Exploratory tests             | `phases/test_and_report.md` |
| 4     | Synthesis & report            | `phases/test_and_report.md` |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You jumped to a fix before understanding the root cause.
- You investigated a single file when the issue spans multiple.
- You reported findings without reproduction steps.

## Verification

Before completing, output a visible block showing: hypothesis type, files analyzed, exploratory tests written and their pass/fail results, and the absolute path of the written report. Confirm the report contains an explicit verdict.

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse hypothesis

Classify the hypothesis complexity:

- **Focused**: targets a specific function, module, or behavior — single researcher sufficient
- **Broad**: spans multiple subsystems or involves architectural concerns — may need multiple research angles
- **External**: involves third-party APIs, protocols, or library behavior — domain research likely needed

### 0.2 Resolve scope

If a `scope:` parameter was extracted, resolve it to a concrete file list. Save to `.mz/task/<task_name>/scope_files.txt`.

### 0.3 Create task directory and state

Task name format: `investigate_<slug>_<HHMMSS>` where slug is a snake_case summary (max 20 chars) of the hypothesis and HHMMSS is current time.

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Investigate: <hypothesis summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Hypothesis type**: <focused / broad / external>
- **Domain research needed**: pending
- **Verdict**: pending
```

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

After setup, read `phases/research.md` and proceed to Phase 1.

______________________________________________________________________

## Error Handling

- **Ambiguous hypothesis**: ask the user to clarify before Phase 1. Never guess the intent.
- **Can't find relevant code**: report what was searched, ask the user to point to specific files.
- **Domain research returns nothing**: note the gap, proceed with codebase-only analysis.
- **Exploratory test can't be written**: report why (no testable assertion, too abstract). Not every hypothesis is testable.
- **Test framework not detected**: ask the user how to run tests.
- **Exploratory test breaks existing tests**: revert immediately, note the conflict in the report.

## State Management

After each phase, update `.mz/task/<task_name>/state.md` with:

- Current phase
- Research findings summary
- Domain research status
- Tests written and their results
- Current verdict assessment
