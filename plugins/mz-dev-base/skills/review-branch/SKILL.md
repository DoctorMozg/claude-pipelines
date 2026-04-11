---
name: review-branch
description: ALWAYS invoke when the user wants to review all changes on the current git branch. Triggers:"review branch","review my changes","check my branch","what did I change","branch review".
argument-hint: '[base-branch (default: main)]'
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

### 1. Validate branch state

Verify the current branch is not `main` or `master`:

```bash
git branch --show-current
```

If on main/master, inform the user there is nothing to review.

### 2. Launch the branch-reviewer agent

Spawn the `branch-reviewer` agent with the following prompt:

```
Review the current branch against <base-branch>.
Analyze all changes file-by-file for bugs, architecture issues, codebase consistency, missing functionality, and test coverage.
Use researcher agents for domain research if the implementation topic is complex.
Save the report to .mz/reviews/ using the naming convention: review_branch_<YYYY_MM_DD>_<branch_name><_vN>.md (append _v2, _v3 etc. if a report with the same base name already exists).
```

Use `subagent_type: "branch-reviewer"` and run it in the foreground so the result is available.

### 3. Report to user

Once the agent completes:

- Show the path to the generated report file
- Print a brief summary of the verdict and key findings (critical bugs, missing tests, etc.)
- If the agent found critical issues, highlight them explicitly

## Techniques

Techniques: delegated to the `branch-reviewer` agent — see its agent definition for diff-walking, test-coverage, and architecture-consistency checks.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 23, not discipline. See Rule 17.

## Red Flags

- You reviewed diff output without checking out or reading the branch's actual file contents.
- You skipped running (or at least reading) the tests that the branch changed.
- The report references files or symbols that do not exist on the branch.

## Verification

Output the report path (`.mz/reviews/review_branch_<YYYY_MM_DD>_<branch><_vN>.md`), confirm the file exists, and print the verdict line plus the top critical findings.
