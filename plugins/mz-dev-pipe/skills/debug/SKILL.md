---
name: debug
description: ALWAYS invoke when the user reports a bug, error, or failing test. Triggers: "debug X", "fix this bug", "why is X failing", "stack trace". When NOT to use: new features (use build), quality polish on known-good code (use polish).
argument-hint: [scope:branch|global|working] <bug report — error message, stack trace, failing test, description, or GitHub issue URL>
allowed-tools: Agent, Bash, Read, Write, Edit, Glob, Grep, TaskCreate, TaskUpdate, TaskGet, TaskList, TaskStop, TaskOutput, AskUserQuestion, WebFetch, WebSearch
---

# Bug Investigation Pipeline

## Overview

Orchestrates a reactive bug investigation: reproduce the bug, diagnose root cause (with optional domain research), get user approval on the diagnosis, write a regression test that fails (TDD), fix minimally, verify, review, and report.

## When to Use

- User reports a bug, error, or failing test with a reproducible symptom.
- Triggers: "debug X", "fix this bug", "why is X failing", "investigate error", "stack trace".
- You have (or can create) a reproducer; the failure is observable.

### When NOT to use

- Building a new feature from scratch — use `build`.
- Polishing already-working code to criteria — use `polish`.
- Map-reduce cleanup across a module — use `optimize`.
- Impact analysis before a refactor — use `blast-radius`.

## Input

- `$ARGUMENTS` — The bug report. Accepts any of:
  - Free text: "the WebSocket reconnection fails on timeout"
  - Failing test name: "test_auth_refresh fails"
  - Stack trace (pasted directly)
  - Error message: "KeyError: 'user_id' in process_payment"
  - GitHub issue URL: `https://github.com/owner/repo/issues/123`

If empty, ask the user what bug to investigate.

## Scope Parameter

Extract `scope:<mode>` from `$ARGUMENTS` (case-insensitive), remove before parsing bug report.

- **`branch`** — `git diff $(git merge-base HEAD <base>)..HEAD --name-only` (try `main`, then `master`). Warn if on base branch.
- **`global`** — All source files, honoring `.gitignore`. Exclude vendored, generated, lock files, >5000 LOC.
- **`working`** — `git diff HEAD --name-only` + `git ls-files --others --exclude-standard`. Warn if empty.
- **Default** — all project files eligible for edits.

`scope:` controls **which files agents may edit**. It does NOT restrict investigation — researchers read any file needed to trace the bug. Tests and linters always run on the full project.

## Constants

- **MAX_FIX_ITERATIONS**: 3 — max fix-verify cycles before escalating
- **MAX_REVIEW_RETRIES**: 2 — max times a review can reject before escalating
- **TASK_DIR**: `.mz/task/` in the project root

## Core Process

### Phase Overview

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

### Phase 0: Setup

1. **Parse input** — classify as `failing_test`, `stack_trace`, `error_message`, `free_text`, or `github_issue`. For GitHub URLs, run `gh issue view <url> --json title,body,comments`; on failure, ask user to paste content.
1. **Resolve scope** — if `scope:` extracted, resolve to file list and save to `.mz/task/<task_name>/scope_files.txt`.
1. **Task directory** — name `debug_<slug>_<HHMMSS>`, create `.mz/task/<task_name>/`. Write `state.md` with Status, Phase, Started, Input type, Reproduced (pending), Root cause (pending), Fix iterations (0), Review retries (0).
1. **Task tracking** — use TaskCreate for each pipeline phase.

After setup, read `phases/investigate.md` and proceed to Phase 1.

### Phase 2.5: User Approval Gate

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

## Techniques

Techniques: delegated to phase files — see Phase Overview table above.
Reference files: grep `references/debugging-patterns.md` for bisection, flaky test, stack trace, or memory leak patterns — do not load the entire file.

## Common Rationalizations

| Rationalization                            | Rebuttal                                                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| "I know what the bug is, I'll just fix it" | "the bug you diagnosed by inspection is the bug you'll miss in a similar codepath tomorrow — write the reproducer first" |
| "can't reproduce, probably flaky"          | "intermittent bugs are the ones that cost real money in prod"                                                            |
| "fix works locally, done"                  | "local environment is not prod; write the regression test that pins the behavior"                                        |

## Red Flags

- You fixed before reproducing the bug.
- You moved on without writing a regression test that pins the fix.
- You assumed the bug was unique to one file without a call-graph check.

## Verification

Output the final report block: reproducer command, root cause with file:line, regression test name, fix diff summary, and green test run confirmation.

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
