---
name: scan-prs
description: ALWAYS invoke when the user wants to check which PRs need attention across repositories. Triggers:"scan PRs","check PRs","what PRs need attention","PR inbox","daily PR report".
argument-hint: '[owner/repo1, owner/repo2, ...]'
allowed-tools: Agent, Bash, Read
---

# Scan PRs

## Overview

Dispatch the `pr-scanner` agent to find pull requests that need the user's attention across multiple GitHub repositories, prioritize them, and fan-out `pr-reviewer` agents on the top priorities.

## When to Use

Triggers: "scan PRs", "check PRs", "what PRs need attention", "PR inbox", "daily PR report".

### When NOT to use

- The user already has a single PR in mind — use `review-pr` directly.
- The user wants to review their own local branch — use `review-branch`.
- No repositories are given and the current directory is not a git repo with a GitHub remote.

## Arguments

`$ARGUMENTS` should be a list of GitHub repositories:

- One per line: `owner/repo`
- Comma-separated: `owner/repo1, owner/repo2`
- As URLs: `https://github.com/owner/repo`

If no argument is provided, detect the current repository from `gh repo view --json nameWithOwner -q .nameWithOwner` and use that.

## Core Process

1. If `$ARGUMENTS` is empty, resolve the current repo via `gh repo view`. If that fails (not a git repo or no remote), ask the user.
1. Launch the `pr-scanner` agent with the repository list as the prompt.
1. The agent scans for PRs where the user is requested for review, mentioned, assigned, or has changes requested on their own PRs.
1. It dispatches `pr-reviewer` agents for the top-5 priority PRs.
1. After completion, display the path to the consolidated report at `.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).

## Techniques

Techniques: delegated to the `pr-scanner` and `pr-reviewer` agents — see their agent definitions for priority ranking, review deduplication, and parallel review fan-out.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 23, not discipline. See Rule 17.

## Red Flags

- You reviewed every PR in the scope instead of filtering to those needing the user's attention.
- You re-reviewed PRs that were already reviewed recently without checking for new commits.
- The top-5 selection was arbitrary rather than priority-ranked by signal strength.

## Verification

Output the consolidated report path (`.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md`), confirm the file exists, and print the per-PR verdict lines for each top-5 dispatch.
