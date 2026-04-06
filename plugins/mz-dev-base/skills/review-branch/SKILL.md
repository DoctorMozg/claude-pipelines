---
name: review-branch
description: Review all changes on the current branch against main — finds bugs, checks architecture, tests, and consistency. Produces a report in .mz/reviews/.
argument-hint: [base-branch (default: main)]
allowed-tools: Agent, Bash, Read, Glob, Grep
---

# Review Current Branch

Launch the `branch-reviewer` agent to perform a comprehensive review of all changes on the current git branch.

## Arguments

- `$ARGUMENTS[0]` (optional) — Base branch to diff against. Defaults to `main`.

## Steps

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
