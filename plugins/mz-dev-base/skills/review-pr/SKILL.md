---
name: review-pr
description: Deep-review a GitHub pull request for bugs, architecture issues, and maintainability. Provide a PR URL or owner/repo#number as argument.
argument-hint: <PR URL or owner/repo#number>
allowed-tools: Agent, Bash, Read
---

# Review PR

Dispatch the `pr-reviewer` agent to perform a thorough review of a GitHub pull request.

## Arguments

`$ARGUMENTS` should be a GitHub PR reference:

- Full URL: `https://github.com/owner/repo/pull/123`
- Short form: `owner/repo#123`

If no argument is provided, ask the user for a PR URL.

## Process

1. Validate that `$ARGUMENTS` contains a PR reference.
1. Launch the `pr-reviewer` agent with the PR reference as the prompt.
1. The agent runs in an isolated worktree, reviews the PR, and writes a report to `.mz/reviews/` using the naming convention: `review_pr_<YYYY_MM_DD>_<owner>_<repo>_<pr_number><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).
1. After the agent completes, display the path to the generated report.
