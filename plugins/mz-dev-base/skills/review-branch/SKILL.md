---
name: review-branch
description: ALWAYS invoke when the user wants to review all changes on the current git branch. Triggers: "review branch", "review my changes", "check my branch", "what did I change", "branch review".
argument-hint: '[base-branch (default: main)]'
model: sonnet
allowed-tools: Agent, Bash, Read, Glob, Grep
---

# Review Current Branch

## Overview

Launch the `branch-reviewer` agent to perform a comprehensive review of all changes on the current git branch against a base branch (default `main`). Produces a report under `.mz/reviews/`.

## When to Use

Triggers: "review branch", "review my changes", "check my branch", "what did I change", "branch review".

### When NOT to use

- You want to review a GitHub PR — use `review-pr` instead.
- The current branch is `main` or `master` — nothing to diff.
- The user wants a scoped review of a single file — read and review it directly.

## Arguments

- `$ARGUMENTS[0]` (optional) — Base branch to diff against. Defaults to `main`.

## Core Process

### Phase 0: Setup

1. `task_name` = `review_branch_<slug>_<HHMMSS>` where `<slug>` is the current branch name (snake_case, max 20 chars) and `<HHMMSS>` is wall-clock time.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `BaseBranch: <base>`, `Branch: <current>`.
1. Emit a visible setup block: `task_name`, base branch, current branch, report dir.

### 1. Validate branch state

Verify the current branch is not `main` or `master`:

```bash
git branch --show-current
```

If on main/master, inform the user there is nothing to review and update `state.md` to `Status: aborted`.

### 2. Launch the branch-reviewer agent

Dispatch `Agent(branch-reviewer)` in the foreground with the following prompt:

```
Review the current branch against <base-branch>.
Analyze all changes file-by-file for bugs, architecture issues, codebase consistency, missing functionality, and test coverage.
Use researcher agents for domain research if the implementation topic is complex.
Save the report to .mz/reviews/ using the naming convention: review_branch_<YYYY_MM_DD>_<branch_name><_vN>.md (append _v2, _v3 etc. if a report with the same base name already exists).
```

Update `state.md` to `Phase: 2` before dispatch and `Phase: 3` after the agent returns.

### 3. Report to user

Once the agent completes:

- Show the path to the generated report file
- Print a brief summary of the verdict and key findings (critical bugs, missing tests, etc.)
- If the agent found critical issues, highlight them explicitly

## Techniques

Techniques: delegated to the `branch-reviewer` agent — see its agent definition for diff-walking, test-coverage, and architecture-consistency checks.

## Common Rationalizations

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You reviewed diff output without checking out or reading the branch's actual file contents.
- You skipped running (or at least reading) the tests that the branch changed.
- The report references files or symbols that do not exist on the branch.

## Verification

Output the report path (`.mz/reviews/review_branch_<YYYY_MM_DD>_<branch><_vN>.md`), confirm the file exists, and print the verdict line plus the top critical findings.

## Error Handling

- **Empty / invalid base-branch argument** → escalate via AskUserQuestion; never guess.
- **Missing tooling** (`git`, `gh`) → detect before dispatch; if absent, escalate via AskUserQuestion with the exact missing command.
- **Empty agent result** (report file missing or empty) → retry the dispatch once with the same prompt; if it fails again, escalate via AskUserQuestion with the failure mode.
- Never guess — on any ambiguity (unknown base branch, detached HEAD, no diff) escalate via AskUserQuestion rather than proceed silently.
