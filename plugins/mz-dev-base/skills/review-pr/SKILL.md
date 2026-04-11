---
name: review-pr
description: ALWAYS invoke when the user wants to review a GitHub pull request. Triggers:"review PR","review pull request","check this PR","PR review". Provide a PR URL or owner/repo#number as argument.
argument-hint: <PR URL or owner/repo#number>
allowed-tools: Agent, Bash, Read
---

# Review PR

## Overview

Dispatch the `pr-reviewer` agent to perform a thorough review of a GitHub pull request in an isolated worktree. Produces a report under `.mz/reviews/` with severity-labeled findings and a verdict.

## When to Use

Triggers: "review PR", "review pull request", "check this PR", "PR review".

### When NOT to use

- The changes live on a local branch, not a GitHub PR — use `review-branch`.
- The user wants to triage many PRs at once — use `scan-prs`.
- The PR reference is ambiguous or missing — ask for a URL or `owner/repo#number`.

## Arguments

`$ARGUMENTS` should be a GitHub PR reference:

- Full URL: `https://github.com/owner/repo/pull/123`
- Short form: `owner/repo#123`

If no argument is provided, ask the user for a PR URL.

## Core Process

1. Validate that `$ARGUMENTS` contains a PR reference.
1. Launch the `pr-reviewer` agent with the PR reference as the prompt.
1. The agent runs in an isolated worktree, reviews the PR, and writes a report to `.mz/reviews/` using the naming convention: `review_pr_<YYYY_MM_DD>_<owner>_<repo>_<pr_number><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).
1. After the agent completes, display the path to the generated report.

## Techniques

Techniques: delegated to the `pr-reviewer` agent — see its agent definition for worktree isolation, diff-plus-context reading, CI-result cross-referencing, and severity labeling.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 23, not discipline. See Rule 17.

## Red Flags

- You reviewed only the diff hunks without reading the surrounding code in the worktree.
- You ignored existing PR comments and re-raised points already discussed.
- You did not cross-reference CI results (lint, type-check, test) before rendering a verdict.

## Verification

Output the report path (`.mz/reviews/review_pr_<YYYY_MM_DD>_<owner>_<repo>_<pr_number><_vN>.md`), confirm the file exists, and print the `VERDICT:` line plus the count of `Critical:` findings.
