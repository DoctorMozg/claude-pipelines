---
name: debug
description: ALWAYS invoke when the user reports a bug, error, or failing test. Triggers: "debug X", "fix this bug", "why is X failing", "investigate error", "stack trace". Reactive bug investigation pipeline — reproduces, diagnoses root cause with optional domain research, writes a regression test (TDD), fixes minimally, verifies, and reviews. Provide a bug report as the argument.
argument-hint: [scope:branch|global|working] <bug report — error message, stack trace, failing test, description, or GitHub issue URL>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Bug Investigation Pipeline

You orchestrate a reactive bug investigation: reproduce the bug, diagnose root cause (with domain research for external dependencies), get user approval on the diagnosis, write a regression test that fails (TDD), fix the root cause minimally, verify, review, and report.

## Input

- `$ARGUMENTS` — The bug report. Accepts any of:
  - Free text: "the WebSocket reconnection fails on timeout"
  - Failing test name: "test_auth_refresh fails"
  - Stack trace (pasted directly)
  - Error message: "KeyError: 'user_id' in process_payment"
  - GitHub issue URL: `https://github.com/owner/repo/issues/123`

If empty, ask the user what bug to investigate.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` if present (case-insensitive). Remove it from the remaining argument text before parsing the bug report.

| Mode      | Resolution                                          | Git command                                                                                                                                                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `branch`  | Files changed on this branch vs base branch         | Detect base: try `main`, then `master`. Run `git diff $(git merge-base HEAD <base>)..HEAD --name-only`. If on the base branch itself (empty diff), warn the user via AskUserQuestion. |
| `global`  | All source files in the repo                        | Honor `.gitignore`. Apply standard exclusions (vendored, generated, lock files, files >5000 LOC).                                                                                     |
| `working` | Uncommitted changes (staged + unstaged + untracked) | `git diff HEAD --name-only` plus `git ls-files --others --exclude-standard`. If no changes exist, warn the user.                                                                      |

**Default** (no `scope:` parameter): all files in the project are eligible for edits.

The `scope:` parameter controls **which files agents may edit**. It does NOT restrict investigation — researchers read any file needed to trace the bug. Tests and linters always run on the full project.

## Constants

- **MAX_FIX_ITERATIONS**: 3 — max fix-verify cycles before escalating
- **MAX_REVIEW_RETRIES**: 2 — max times a review can reject before escalating
- **TASK_DIR**: `.mz/task/` in the project root

## Phase Overview

| Phase | Goal                       | Details                    |
| ----- | -------------------------- | -------------------------- |
| 0     | Setup                      | Inline below               |
| 1     | Reproduce                  | `phases/investigate.md`    |
| 2     | Diagnose + domain research | `phases/investigate.md`    |
| 2.5   | User approval              | Inline below               |
| 3     | Regression test (TDD)      | `phases/fix_and_verify.md` |
| 4     | Fix                        | `phases/fix_and_verify.md` |
| 5     | Verify & review            | `phases/fix_and_verify.md` |
| 6     | Report                     | `phases/fix_and_verify.md` |

Read the relevant phase file when you reach that phase. Do not read both phase files upfront.

______________________________________________________________________

## Phase 0: Setup

### 0.1 Parse input

Classify the input into one of: `failing_test`, `stack_trace`, `error_message`, `free_text`, `github_issue`.

If GitHub issue URL: run `gh issue view <url> --json title,body,comments` and extract bug details. If that fails, ask the user to paste the issue content.

### 0.2 Resolve scope

If a `scope:` parameter was extracted, resolve it to a concrete file list. Save to `.mz/task/<task_name>/scope_files.txt`. This constrains which files coder agents may edit.

### 0.3 Create task directory and state

Derive task name: short snake_case (max 30 chars) from bug summary.

```bash
mkdir -p .mz/task/<task_name>
```

Write `.mz/task/<task_name>/state.md`:

```markdown
# Debug: <bug summary>
- **Status**: started
- **Phase**: setup
- **Started**: <timestamp>
- **Input type**: <failing_test | stack_trace | error_message | free_text | github_issue>
- **Reproduced**: pending
- **Root cause**: pending
- **Fix iterations**: 0
- **Review retries**: 0
```

### 0.4 Create task tracking

Use TaskCreate for each pipeline phase.

After setup, read `phases/investigate.md` and proceed to Phase 1.

______________________________________________________________________

## Phase 2.5: User Approval Gate

**This orchestrator** (not a subagent) must present to the user via AskUserQuestion. This step is interactive and must not be delegated.

Use AskUserQuestion with:

```
Bug investigation complete. Review the diagnosis before I proceed:

## Bug
<original bug description>

## Reproduction
<how the bug was reproduced, or "static confirmation only">

## Root Cause
<diagnosed root cause with file:line references>

## Proposed Fix
<minimal fix description>

## External Context
<domain research findings — omit if none>

Reply 'approve' to proceed with regression test + fix, 'reject' to abort, or provide feedback.
```

**Response handling**:

- **"approve"** → read `phases/fix_and_verify.md`, proceed to Phase 3.
- **"reject"** → update state to `aborted_by_user` and stop. Do not proceed.
- **Feedback** → re-run diagnosis (Phase 2) incorporating the user's input, then return to this gate and re-present **via AskUserQuestion** using the same format. This is a loop — repeat until the user explicitly approves. Never proceed to Phase 3 without explicit approval.

______________________________________________________________________

## Error Handling

- **Can't reproduce**: report what was tried and findings via AskUserQuestion. Ask for more context. Do NOT proceed with guesswork.
- **Ambiguous input**: ask the user to clarify before Phase 1.
- **GitHub issue fetch fails**: ask the user to paste the bug description.
- **No test framework detected**: ask the user how to run tests.
- **Domain research returns nothing**: note the gap and proceed with codebase-only diagnosis.
- **Fix makes things worse**: revert immediately and try a different approach.
- Always save state before spawning agents.

## State Management

After each phase/iteration, update `.mz/task/<task_name>/state.md` with current phase, reproduction status, iteration counts, and files modified.
