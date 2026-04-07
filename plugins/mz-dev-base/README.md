# mz-dev-base

Foundation plugin for Claude Code — standalone agents, coding rules, and utility skills for everyday development workflows.

## Installation

```bash
claude plugin marketplace add DoctorMozg/claude-pipelines
claude plugin install mz-dev-base
```

## Skills

### `/review-branch` — Branch Review

Reviews all changes on the current branch against its base branch. Analyzes every modified file for bugs, architecture issues, missing functionality, and test coverage gaps. Produces a structured report saved to `.mz/reviews/`.

```
/review-branch              # compare against main
/review-branch develop      # compare against develop
```

### `/review-pr` — Pull Request Review

Deep-reviews a GitHub PR: reads the diff, comments, and discussions, checks out the code in an isolated worktree, reviews for bugs and maintainability, cross-references existing feedback, and writes a report.

```
/review-pr https://github.com/owner/repo/pull/123
/review-pr owner/repo#123
```

### `/scan-prs` — PR Scanner

Scans GitHub repositories for PRs needing your attention — review requested, mentioned, assigned, or your own PRs with changes requested. Dispatches deep reviewers for the top 5 priority PRs and produces a consolidated daily report.

```
/scan-prs owner/repo1, owner/repo2
```

### `/deep-research` — Multi-Agent Research

Splits a research topic into domains, dispatches parallel researcher agents that each scan 20-100 web pages, then synthesizes findings into a comprehensive report.

```
/deep-research best practices for gRPC error handling in Go
/deep-research comparison of vector databases for RAG pipelines
```

### `/init-rules` — Rule Installer

Detects project languages and installs relevant coding rules to `.claude/rules/` (project scope) or `~/.claude/rules/` (global scope). Rules cover code quality, typing, git conventions, edit safety, and language-specific patterns.

```
/init-rules                 # project scope, auto-detect languages
/init-rules global          # user scope
/init-rules project --force # overwrite existing rules
```

## Agents

Agents are specialized workers that can be invoked directly or used by skills.

| Agent                | Purpose                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| **code-reviewer**    | Reviews code changes for bugs, security vulnerabilities, performance issues, and maintainability |
| **branch-reviewer**  | Analyzes all branch changes file-by-file, delegates to researcher for complex domain topics      |
| **pr-reviewer**      | Deep PR review in an isolated worktree with structured markdown report                           |
| **pr-scanner**       | Scans repos for PRs needing attention, dispatches pr-reviewer for top priorities                 |
| **researcher**       | Multi-source research with web search, source verification, and structured reports               |
| **technical-writer** | Creates and improves technical documentation grounded in actual code                             |

## Rules

Available via `/init-rules`. Each rule is a focused guideline installed as a `.md` file in your rules directory.

| Rule                       | Focus                                                   |
| -------------------------- | ------------------------------------------------------- |
| **code-quality**           | Clean code principles, meaningful naming, function size |
| **coding-standards**       | Project-level conventions and consistency               |
| **strict-typing**          | Type hints, TypedDict, Protocol usage                   |
| **python-conventions**     | Python-specific patterns, pytest fixtures, Pydantic     |
| **edit-safety**            | Re-read before edit, verify after, no stale context     |
| **context-safety**         | Context decay awareness, file read budgets              |
| **self-evaluation**        | Verify before reporting, two-perspective review         |
| **agent-workflow**         | Sub-agent swarming, phased execution                    |
| **git-conventions**        | Commit messages, branch hygiene                         |
| **housekeeping**           | File hygiene, checkpoint suggestions                    |
| **pre-commit-conventions** | Pre-commit hook patterns                                |

## License

MIT
