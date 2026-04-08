---
name: scan-prs
description: ALWAYS invoke when the user wants to check which PRs need attention across repositories. Triggers: "scan PRs", "check PRs", "what PRs need attention", "PR inbox", "daily PR report". Scans GitHub repositories for PRs needing review and produces a prioritized daily report. Provide repository list as argument.
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
1. After completion, display the path to the consolidated report at `.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).
