# mz-dev-git

Git and GitHub review pipelines for Claude Code. Multi-lens deep review of local branch changes and GitHub pull requests, plus daily PR triage.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-dev-git
```

## Dependencies

`mz-dev-git` is **functionally self-contained** for branch and PR review but **dispatches `pipeline-web-researcher` from `mz-dev-pipe`** when reviewers encounter unfamiliar domain topics that need authoritative external sources. Install `mz-dev-pipe` for the full experience:

```bash
claude plugin install mz-dev-pipe
```

If `mz-dev-pipe` is absent, the reviewers skip the optional web-research step and continue with codebase-only analysis. No hard failure.

GitHub-PR skills additionally require the `gh` CLI authenticated, or `$GITHUB_TOKEN` set, or a GitHub MCP server exposed in the session.

## Skills

### `/review-branch` — Branch Review

Reviews all changes on the current branch against its base branch. Walks every modified file, runs five parallel code-review lenses (bugs, security, architecture, performance, maintainability), optionally consults `pipeline-web-researcher` for unfamiliar domains, and produces a structured report saved to `.mz/reviews/`.

```
/review-branch              # compare against main
/review-branch develop      # compare against develop
```

**Pipeline**: branch-info-collector (git metadata + prior reviews) → branch-reviewer fan-out (5 code-lens agents in parallel + optional web research) → consolidated findings report.

### `/github-review-pr` — Pull Request Review

Deep-reviews a GitHub PR in an isolated worktree. Reads the diff, comments, and discussions, runs the same multi-lens analysis as `/review-branch`, cross-references existing reviewer feedback, and writes a severity-labeled report.

```
/github-review-pr https://github.com/owner/repo/pull/123
/github-review-pr owner/repo#123
```

**Pipeline**: github-pr-reviewer (worktree setup + PR metadata) → branch-reviewer fan-out on the worktree → consolidated report with verdict and Critical-finding count.

### `/github-scan-prs` — PR Triage

Scans GitHub repositories for PRs needing your attention — review requested, mentioned, assigned, or your own PRs with changes requested. Fans out one haiku scorer per PR and produces a tier-ranked daily triage report. Deep reviews are not part of this skill — for any single PR, run `/github-review-pr` separately.

```
/github-scan-prs                              # current repo only
/github-scan-prs owner/repo1, owner/repo2     # explicit list
```

**Pipeline**: github-pr-data-fetcher (multi-repo PR list with dedup + smoke tests) → github-pr-scanner orchestrator → per-PR github-pr-info-scorer (haiku, parallel waves of 6) → tier-ranked report.

## Agents

Specialized worker agents used by the skills above. You don't invoke these directly — the skills orchestrate them.

| Agent                         | Role                                                                                            |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| **branch-reviewer**           | Top-level orchestrator. Walks each changed file, fans out 5 code-lens agents, merges findings   |
| **branch-info-collector**     | Pipeline collector — runs git metadata commands and scans for prior review reports              |
| **github-pr-reviewer**        | Top-level PR orchestrator. Sets up isolated worktree, dispatches branch-reviewer, writes report |
| **github-pr-scanner**         | Multi-repo PR triage orchestrator. Fans out github-pr-info-scorer per PR, produces tier ranking |
| **github-pr-data-fetcher**    | Pipeline collector — bulk PR list + dedup + zero-result smoke tests across multiple repos       |
| **github-pr-info-scorer**     | Per-PR haiku scorer — lightweight metadata + complexity + answered/unanswered classification    |
| **code-lens-bugs**            | Pipeline lens — scans diff for logic errors, off-by-one, null access, races, resource leaks     |
| **code-lens-security**        | Pipeline lens — scans for injection, auth bypass, secret exposure, SSRF, IDOR, weak crypto      |
| **code-lens-architecture**    | Pipeline lens — scans for SOLID violations, coupling, layering, pattern drift, god classes      |
| **code-lens-performance**     | Pipeline lens — scans for N+1, blocking I/O in async, missing indexes, O(n²) hot paths          |
| **code-lens-maintainability** | Pipeline lens — scans for unclear naming, complexity, magic values, dead code, duplication      |

All five `code-lens-*` agents and the four `github-pr-*` collectors/scorers are **pipeline-only** — dispatched exclusively by their orchestrators. They are not user-invocable.

## Cross-plugin dispatch

`branch-reviewer.md` and `github-pr-reviewer.md` reference `pipeline-web-researcher`, which lives in `mz-dev-pipe`. Claude Code resolves agent names across all loaded plugins, so the dispatch works as long as both plugins are installed. Documenting the dependency here rather than enforcing it via plugin manifest — Claude Code's plugin format does not currently support a `dependsOn` field.

## License

MIT
