---
name: scan-prs
description: ALWAYS invoke when the user wants to check which PRs need attention across repositories. Triggers:"scan PRs","check PRs","what PRs need attention","PR inbox","daily PR report".
argument-hint: '[owner/repo1, owner/repo2, ...]'
model: sonnet
allowed-tools: Agent, Bash, Read
---

# Scan PRs

## Overview

Dispatch the `pr-scanner` agent to find pull requests that need the user's attention across multiple GitHub repositories, fan out per-PR haiku scorers for every PR, and produce a prioritized triage report. Deep code reviews are not part of this skill — for a thorough review on any single PR in the report, the user runs `/review-pr <url>` separately.

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
1. Write `state.md` with `Status: running`, `Phase: 0`, `Started: <ISO timestamp>`, `Repos: [<list>]`, `ScannedPRs: 0`, `ScoredPRs: 0`.
1. Emit a visible setup block: `task_name`, repo list, report dir (`.mz/reviews/`).

### 1. Dispatch

1. Launch the `pr-scanner` agent with the repository list as the prompt.
1. The agent scans for PRs where the user is requested for review, mentioned, assigned, or has changes requested on their own PRs, then fans out one `pr-info-scorer` haiku agent per PR (in parallel waves of up to 6) to gather metadata, complexity signals, and unanswered-question state.
1. Every PR returned by the scan is scored into one of three tiers — Tier 1 (directly asked, unanswered), Tier 2 (review or action requested), or Tier 3 (informational) — and ranked within its tier by complexity and age.
1. After completion, display the path to the triage report at `.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md` (append `_v2`, `_v3` etc. if a report with the same base name already exists).

## Techniques

Techniques: delegated to the `pr-scanner`, `github-pr-data-fetcher`, and `pr-info-scorer` agents — see their agent definitions for bulk PR listing, per-PR haiku triage, and tier-based ranking.

## Common Rationalizations

N/A — collaboration/reference skill, not discipline.

## Red Flags

- You produced a triage report without scoring every PR the fetcher returned (top-N truncation is a bug here).
- You dispatched the `pr-reviewer` agent from this skill — deep reviews belong to `/review-pr`, not the triage flow.
- You let a Tier 2 or Tier 3 item outrank a Tier 1 item in the report (tier boundaries are absolute; complexity only orders within a tier).

## Verification

Output the triage report path (`.mz/reviews/pr_scan_<YYYY_MM_DD>_<repo_names><_vN>.md`), confirm the file exists, and confirm Tier 1 items (if any) appear above Tier 2 and Tier 3 in the report. The report should end with a `How to Deep-Review` footer pointing users to `/review-pr <url>` for any single PR that warrants a thorough read.

## Error Handling

- **Empty args** with no detectable current repo → before escalating, try the fallback chain for `gh repo view`: (1) `mcp__*github*` MCP tools if exposed, (2) direct REST API (`curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/{owner}/{repo}"`). Only escalate via AskUserQuestion after all three tiers fail; never guess.
- **`gh` unavailable** (not installed, not authenticated, rate-limited) → delegate to the fallback chain before blocking. The `pr-scanner` agent has its own `GitHub Access Fallback` section that governs downstream calls. Only escalate via AskUserQuestion if MCP and REST tiers also fail.
- **Missing tooling** (`Agent` tool absent) → escalate via AskUserQuestion with the exact missing command.
- **Empty scanner result** (zero PRs returned or no priority-ranked list) → check the scanner's `pr_data.md` / report for `ZERO RESULTS` disclosure tokens before trusting:
  - `ZERO RESULTS VERIFIED` (per-repo smoke test passed) → report "no PRs need attention" and exit cleanly.
  - `ZERO RESULTS UNVERIFIED` or `ZERO RESULTS GLOBAL` → do NOT treat as a clean inbox; surface the warning in the final output and prompt the user to verify the GitHub username and repo list via AskUserQuestion before a silent "all clear" masks a real misconfiguration.
  - No `ZERO RESULTS` token present with an empty list → retry the scan once with the same repo list; if still empty, escalate via AskUserQuestion. Malformed agent responses also retry once then escalate.
- Never guess — on any ambiguity (unresolvable repo, invalid URL, missing auth) escalate via AskUserQuestion rather than proceed silently.

## State Management

After Phase 1 completes, update `.mz/task/<task_name>/state.md` with:

- `Status:` `complete` | `complete_with_concerns` | `blocked` | `no_prs_found`
- `Phase:` `1`
- `ScannedPRs:` total PR count from the fetcher artifact
- `ScoredPRs:` count of PRs with valid `pr-info-scorer` artifacts (should equal ScannedPRs on a clean run)
- `ReportPath:` absolute path to the triage report

Never rely on conversation memory — the state file is the source of truth if the session is interrupted.
