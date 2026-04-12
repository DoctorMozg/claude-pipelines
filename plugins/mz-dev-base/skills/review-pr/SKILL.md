---
name: review-pr
description: ALWAYS invoke when the user wants to review a GitHub pull request. Triggers:"review PR","review pull request","check this PR","PR review". Provide a PR URL or owner/repo#number as argument.
argument-hint: <PR URL or owner/repo#number>
model: sonnet
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

### Phase 0: Setup

1. Parse `$ARGUMENTS`. If the PR reference is empty or malformed, escalate via AskUserQuestion — never guess, never fabricate a PR URL.
1. Normalize the reference to `<owner>_<repo>_<pr_number>` form.
1. `task_name` = `review_pr_<slug>_<HHMMSS>` where `<slug>` is `<owner>_<repo>_<pr_number>` truncated to 20 chars, snake_case, and `<HHMMSS>` is wall-clock time.
1. Create `.mz/task/<task_name>/`.
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `PR: <reference>`, `Owner: <owner>`, `Repo: <repo>`, `Number: <pr_number>`.
1. Emit a visible setup block: `task_name`, PR reference, report dir (`.mz/reviews/`).

### 1. Dispatch

1. Validate that the normalized PR reference points to an accessible PR (via `gh pr view`). On failure, escalate via AskUserQuestion.
1. Launch the `pr-reviewer` agent with the PR reference as the prompt.
1. The agent runs in an isolated worktree, reviews the PR, and writes a report to `.mz/reviews/` using the naming convention: `review_pr_<YYYY_MM_DD>_<owner>_<repo>_<pr_number><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).
1. After the agent completes, update `state.md` to `Status: complete`, `Phase: 1`, and display the path to the generated report.

## Techniques

Techniques: delegated to the `pr-reviewer` agent — see its agent definition for worktree isolation, diff-plus-context reading, CI-result cross-referencing, and severity labeling.

## Common Rationalizations

N/A — collaboration/reference skill per Rule 17, not discipline. See Rule 17.

## Red Flags

- You reviewed only the diff hunks without reading the surrounding code in the worktree.
- You ignored existing PR comments and re-raised points already discussed.
- You did not cross-reference CI results (lint, type-check, test) before rendering a verdict.

## Verification

Output the report path (`.mz/reviews/review_pr_<YYYY_MM_DD>_<owner>_<repo>_<pr_number><_vN>.md`), confirm the file exists, and print the `VERDICT:` line plus the count of `Critical:` findings.

## Error Handling

- **Empty / malformed PR argument** → escalate via AskUserQuestion; never guess, never fabricate a PR URL.
- **Missing tooling** (`gh` not installed, not authenticated, `git worktree` unavailable, `Agent` tool absent) → escalate via AskUserQuestion with the exact missing command.
- **Empty agent result** (report file missing, empty, or no `VERDICT:` line) → retry the dispatch once with the same prompt; if still empty, escalate via AskUserQuestion with the failure mode.
- Never guess — on any ambiguity (inaccessible PR, 404, merge conflict in worktree, missing base ref) escalate via AskUserQuestion rather than proceed silently.
