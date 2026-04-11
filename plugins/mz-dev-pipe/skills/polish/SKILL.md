---
name: polish
description: ALWAYS invoke when the user wants to polish code against criteria — fix failing tests, meet quality standards. Triggers: "polish X", "make tests pass", "fix failing tests". When NOT to use: new feature (use build), single bug (use debug).
argument-hint: [scope:branch|global|working] <completion criteria — what must pass, what must be fixed, what must work>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Polishing Pipeline

## Overview

Orchestrates iterative polish of existing code against specific completion criteria. Unlike `build` which builds from scratch, polish works with what's already there — running tests, diagnosing failures, fixing issues with review loops, and optimizing.

## When to Use

- User has existing code that needs to meet specific criteria or quality standards.
- Triggers: "polish X", "make tests pass", "fix failing tests", "clean up the code", "finish this implementation".
- Code exists but is failing tests, lint, or quality gates.

### When NOT to use

- Starting a new feature from scratch — use `build`.
- A single isolated bug with a reproducer — use `debug`.
- Read-only verification with no fix intent — use `verify`.
- Map-reduce dead-code cleanup — use `optimize`.

## Input

- `$ARGUMENTS` — The completion criteria. This can be:
  - "All tests in test_foo.py must pass"
  - "Pre-commit hooks must pass on all changed files"
  - "The WebSocket reconnection must handle timeout correctly"
  - "Fix all failing tests and clean up the implementation"
  - Any combination of pass/fail criteria and behavioral requirements

If empty, ask the user what needs to be polished.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` (case-insensitive), remove before parsing criteria.

- **`branch`** — `git diff $(git merge-base HEAD <base>)..HEAD --name-only` (try `main`, then `master`). Warn if on base branch.
- **`global`** — All source files, honoring `.gitignore`. Exclude vendored, generated, lock, >5000 LOC.
- **`working`** — `git diff HEAD --name-only` + `git ls-files --others --exclude-standard`. Warn if empty.
- **Default** — all project files eligible for edits.

`scope:` controls **which files agents may edit**. Tests and linters always run on the full project. Criteria determine **what to verify**; scope determines **where fixes may be applied**.

## Constants

- **MAX_FIX_ITERATIONS**: 5 — max code-test-review cycles before escalating
- **MAX_REVIEW_RETRIES**: 3 — max times a review can fail before escalating
- **TASK_DIR**: `.mz/task/` in the project root

## Core Process

### Phase Overview

| Phase | Goal                 | Details                             |
| ----- | -------------------- | ----------------------------------- |
| 0     | Setup                | Inline below                        |
| 1     | Initial Assessment   | `phases/assess_and_fix.md`          |
| 2     | Quick Fixes          | `phases/assess_and_fix.md`          |
| 3     | Research (if needed) | `phases/assess_and_fix.md`          |
| 4     | Fix-Test-Review Loop | `phases/fix_review_and_finalize.md` |
| 5     | Optimization         | `phases/fix_review_and_finalize.md` |
| 6     | Final Verification   | `phases/fix_review_and_finalize.md` |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

### Phase 0: Setup

1. **Resolve scope** — if `scope:` extracted, resolve to a concrete file list and save to `.mz/task/<task_name>/scope_files.txt`. Otherwise all project files eligible.
1. **Parse criteria** — break input into a checklist of discrete, verifiable criteria (e.g. "all tests pass", "pre-commit clean", "no debug prints in src/").
1. **Task name** — `polish_<slug>_<HHMMSS>` (slug = snake_case of criteria, max 20 chars).
1. **Task dir & state** — create `.mz/task/<task_name>/`, write `state.md` with Status, Phase, Started, Iteration (0), and the criteria checklist.
1. **Task tracking** — TaskCreate per pipeline phase. Then read `phases/assess_and_fix.md` and proceed to Phase 1.

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.

## Common Rationalizations

| Rationalization                      | Rebuttal                                                 |
| ------------------------------------ | -------------------------------------------------------- |
| "good enough, ship"                  | "polish is the last line of defense before users see it" |
| "edge cases are rare"                | "every bug report you've ever gotten is an edge case"    |
| "tests are green, refactor can wait" | "green-test refactor debt compounds"                     |

## Red Flags

- Edge cases were deferred to "next sprint" instead of handled now.
- Code was declared "good enough" without a final criteria sweep.
- Polish was equated with refactor — criteria drifted mid-loop.

## Verification

Output the final criteria checklist with every item checked, along with the test run status, lint status, and iteration count. Any unchecked item blocks completion.

## Error Handling

- If a test framework isn't detected, ask the user how to run tests.
- If a criterion can't be verified programmatically, ask the user for a verification command.
- If research fails to identify root cause after 2 attempts, ask the user for context.
- Always save state before spawning agents.
- If a fix makes things worse (more criteria fail than before), revert the change immediately and try a different approach.

## State Management

After each phase/iteration, update `.mz/task/<task_name>/state.md` with:

- Current phase and iteration count
- Criteria checklist (checked/unchecked)
- Files modified so far
- Any escalation notes

Track cumulative file changes across iterations so the optimizer knows the full scope.
