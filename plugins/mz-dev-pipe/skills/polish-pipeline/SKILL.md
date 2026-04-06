---
name: polish-pipeline
description: Polishes existing code to meet specific completion criteria — runs tests, iterates fixes with review, optimizes code. Provide criteria as the argument.
argument-hint: [scope:branch|global|working] <completion criteria — what must pass, what must be fixed, what must work>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Code Polishing Pipeline

You are an orchestrator that takes existing code and polishes it until it meets specific completion criteria. Unlike the dev-pipeline which builds from scratch, you work with what's already there — running tests, diagnosing failures, fixing issues, reviewing changes, and optimizing code.

## Input

- `$ARGUMENTS` — The completion criteria. This can be:
  - "All tests in test_foo.py must pass"
  - "Pre-commit hooks must pass on all changed files"
  - "The WebSocket reconnection must handle timeout correctly"
  - "Fix all failing tests and clean up the implementation"
  - Any combination of pass/fail criteria and behavioral requirements

If empty, ask the user what needs to be polished.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing completion criteria.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, files >5000 LOC).                                                                                     |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): all files in the project are eligible for edits (existing behavior).

The `scope:` parameter controls **which files agents may edit**. It does NOT restrict verification — tests and linters always run on the full project to catch regressions. The criteria determine **what to verify**; the scope determines **where fixes may be applied**.

Example: `scope:branch "all tests pass"` → only edit files changed on this branch, but run the full test suite to verify.

## Constants

- **MAX_FIX_ITERATIONS**: 5 — max code-test-review cycles before escalating
- **MAX_REVIEW_RETRIES**: 3 — max times a review can fail before escalating
- **TASK_DIR**: `.mz/task/` in the project root

## Phase Overview

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

______________________________________________________________________

## Phase 0: Setup

### 0.1 Resolve scope

If a `scope:` parameter was extracted, resolve it to a concrete file list using the git commands from the Scope Parameter table. Save the list to `.mz/task/<task_name>/scope_files.txt` (one path per line). This list constrains which files coder and optimizer agents may edit in later phases.

If no `scope:` parameter was given, skip this step — all project files are eligible.

### 0.2 Parse criteria

Break the remaining input into a checklist of discrete, verifiable criteria. Each criterion must be something you can check programmatically or by reading code.

Example input: "All tests pass, pre-commit clean, no debug prints in src/"
→ Criteria:

1. All tests in scope pass
1. Pre-commit hooks pass
1. No `print()` statements in `src/` (excluding intentional logging)

### 0.3 Derive task name

Short snake_case name (max 30 chars) from the criteria summary.

### 0.4 Create task directory and state

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Polish: <criteria summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Iteration**: 0
- **Criteria**:
  1. [ ] <criterion 1>
  2. [ ] <criterion 2>
  ...
```

### 0.5 Create task tracking

Use TaskCreate for each pipeline phase.

After setup completes, read `phases/assess_and_fix.md` and proceed to Phase 1.

______________________________________________________________________

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
