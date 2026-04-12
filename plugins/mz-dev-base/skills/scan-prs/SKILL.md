---
name: scan-prs
description: ALWAYS invoke when the user wants to check which PRs need attention across repositories. Triggers:"scan PRs","check PRs","what PRs need attention","PR inbox","daily PR report".
argument-hint: '[owner/repo1, owner/repo2, ...]'
model: sonnet
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

### Phase 0: Setup

1. Parse `$ARGUMENTS` — list of GitHub repositories. If empty, resolve current repo via `gh repo view --json nameWithOwner -q .nameWithOwner`; if that fails, escalate via AskUserQuestion. Never guess.
1. `task_name` = `scan_prs_<slug>_<HHMMSS>` where `<slug>` is a snake_case summary of the repo list (max 20 chars, e.g. `owner_repo` or `multi_repo`) and `<HHMMSS>` is wall-clock time.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Repos: [<list>]`, `ScannedPRs: 0`, `ReviewedPRs: 0`.
1. Emit a visible setup block: `task_name`, repo list, report dir (`.mz/reviews/`).

### 1. Dispatch

1. Launch the `pr-scanner` agent with the repository list as the prompt.
1. The agent scans for PRs where the user is requested for review, mentioned, assigned, or has changes requested on their own PRs.
1. It dispatches `pr-reviewer` agents for the top-5 priority PRs.
1. After completion, display the path to the consolidated report at `.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).

## Techniques

Techniques: delegated to the `pr-scanner` and `pr-reviewer` agents — see their agent definitions for priority ranking, review deduplication, and parallel review fan-out.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 17, not discipline. See Rule 17.

## Red Flags

- You reviewed every PR in the scope instead of filtering to those needing the user's attention.
- You re-reviewed PRs that were already reviewed recently without checking for new commits.
- The top-5 selection was arbitrary rather than priority-ranked by signal strength.

## Verification

Output the consolidated report path (`.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md`), confirm the file exists, and print the per-PR verdict lines for each top-5 dispatch.

## Error Handling

- **Empty args** with no detectable current repo → escalate via AskUserQuestion; never guess.
- **Missing tooling** (`gh` not installed, not authenticated, or `Agent` tool absent) → escalate via AskUserQuestion with the exact missing command.
- **Empty scanner result** (zero PRs returned or no priority-ranked list) → retry the scan once with the same repo list; if still empty, report "no PRs need attention" and exit cleanly. For a malformed agent response, retry once then escalate via AskUserQuestion.
- Never guess — on any ambiguity (unresolvable repo, invalid URL, missing auth) escalate via AskUserQuestion rather than proceed silently.
