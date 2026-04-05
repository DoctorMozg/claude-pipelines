---
name: scan-prs
description: Scan GitHub repositories for PRs needing your attention and produce a prioritized daily report. Provide repository list as argument.
argument-hint: '[owner/repo1, owner/repo2, ...]'
allowed-tools: Agent, Bash, Read
---

# Scan PRs

Dispatch the `pr-scanner` agent to find pull requests that need your attention across multiple repositories.

## Arguments

`$ARGUMENTS` should be a list of GitHub repositories:

- One per line: `owner/repo`
- Comma-separated: `owner/repo1, owner/repo2`
- As URLs: `https://github.com/owner/repo`

If no argument is provided, detect the current repository from `gh repo view --json nameWithOwner -q .nameWithOwner` and use that.

## Process

1. If `$ARGUMENTS` is empty, resolve the current repo via `gh repo view`. If that fails (not a git repo or no remote), ask the user.
1. Launch the `pr-scanner` agent with the repository list as the prompt.
1. The agent scans for PRs where you are requested for review, mentioned, assigned, or have changes requested on your own PRs.
1. It dispatches `pr-reviewer` agents for the top-5 priority PRs.
1. After completion, display the path to the consolidated report at `.mz/reviews/<date>_REPORT.md`.
